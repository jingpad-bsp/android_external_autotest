#!/usr/bin/env python
# Copyright 2015 The Chromium OS Authors. All rights reserved.
# Use of this source code is governed by a BSD-style license that can be
# found in the LICENSE file.

"""Create e-mail reports of the Lab's DUT inventory.

Gathers a list of all DUTs of interest in the Lab, segregated by
board and pool, and determines whether each DUT is working or
broken.  Then, send one or more e-mail reports summarizing the
status to e-mail addresses provided on the command line.

usage:  lab_inventory.py [ options ] [ board ... ]

Options:
--duration / -d <hours>
    How far back in time to search job history to determine DUT
    status.

--board-notify <address>[,<address>]
    Send the "board status" e-mail to all the specified e-mail
    addresses.

--pool-notify <address>[,<address>]
    Send the "pool status" e-mail to all the specified e-mail
    addresses.

--logdir <directory>
    Log progress and actions in a file under this directory.  Text
    of any e-mail sent will also be logged in a timestamped file in
    this directory.

--print
    Suppress all logging and sending e-mail.  Instead, write the
    output that would be generated onto stdout.

<board> arguments:
    With no arguments, gathers the status for all boards in the lab.
    With one or more named boards on the command line, restricts
    reporting to just those boards.

"""


import argparse
import logging
import logging.handlers
import os
import sys
import time

import common
from autotest_lib.client.common_lib import time_utils
from autotest_lib.server import frontend
from autotest_lib.site_utils import gmail_lib
from autotest_lib.site_utils import status_history
from autotest_lib.site_utils.suite_scheduler import constants


# The pools in the Lab that are actually of interest.
#
# These are general purpose pools of DUTs that are considered
# identical for purposes of testing.  That is, a device in one of
# these pools can be shifted to another pool at will for purposes
# of supplying test demand.
#
# Devices in these pools are not allowed to have special-purpose
# attachments, or to be part of in any kind of custom fixture.
# Devices in these pools are also required to reside in areas
# managed by the Platforms team (i.e. at the time of this writing,
# only in "Atlantis" or "Destiny").
#
# _CRITICAL_POOLS - Pools that must be kept fully supplied in order
#     to guarantee timely completion of tests from builders.
# _SPARE_POOL - A low priority pool that is allowed to provide
#     spares to replace broken devices in the critical pools.
# _MANAGED_POOLS - The set of all the general purpose pools
#     monitored by this script.

_CRITICAL_POOLS = ['bvt', 'cq']
_SPARE_POOL = 'suites'
_MANAGED_POOLS = _CRITICAL_POOLS + [_SPARE_POOL]


# _DEFAULT_DURATION:
#     Default value used for the --duration command line option.
#     Specifies how far back in time to search in order to determine
#     DUT status.

_DEFAULT_DURATION = 24


# _LOGDIR:
#     Relative path used in the calculation of the default setting
#     for the --logdir option.  The full path path is relative to
#     the root of the autotest directory, as determined from
#     sys.argv[0].
# _LOGFILE:
#     Basename of a file to which general log information will be
#     written.
# _LOG_FORMAT:
#     Format string for log messages.

_LOGDIR = os.path.join('logs', 'dut-data')
_LOGFILE = 'lab-inventory.log'
_LOG_FORMAT = '%(asctime)s | %(levelname)-10s | %(message)s'


class _PoolCounts(object):
    """Maintains a set of `HostJobHistory` objects for a pool.

    The collected history objects are nominally all part of a single
    scheduling pool of DUTs.  The collection maintains a count of
    working DUTs, a count of broken DUTs, and a total count.

    Performance note:  The methods `get_working()` and
    `get_broken()` (but not `get_total()`) are potentially
    expensive.  The first time they're called, they must make a
    potentially expensive set of database queries.  The results of
    the queries are cached in the individual `HostJobHistory`
    objects, so only the first call actually pays the cost.

    This class is deliberately constructed to delay that cost until
    the accessor methods are called (rather than to query in
    `record_host()`) so that it's possible to construct a complete
    `_LabInventory` without making the expensive queries at creation
    time.  `_populate_board_counts()`, below, relies on this
    behavior.

    """

    def __init__(self):
        self._histories = []


    def record_host(self, host_history):
        """Add one `HostJobHistory` object to the collection.

        @param host_history The `HostJobHistory` object to be
                            remembered.

        """
        self._histories.append(host_history)


    def get_working(self):
        """Return the number of working DUTs in the collection."""
        return len([h for h in self._histories
                        if h.last_diagnosis()[0] == status_history.WORKING])


    def get_broken(self):
        """Return the number of broken DUTs in the collection."""
        return len([h for h in self._histories
                        if h.last_diagnosis()[0] != status_history.WORKING])


    def get_total(self):
        """Return the total number of DUTs in the collection."""
        return len(self._histories)


class _BoardCounts(object):
    """Maintains a set of `HostJobHistory` objects for a board.

    The collected history objects are nominally all of the same
    board.  The collection maintains a count of working DUTs, a
    count of broken DUTs, and a total count.  The counts can be
    obtained either for a single pool, or as a total across all
    pools.

    DUTs in the collection must be assigned to one of the pools
    in `_MANAGED_POOLS`.

    The `get_working()` and `get_broken()` methods rely on the
    methods of the same name in _PoolCounts, so the performance
    note in _PoolCounts applies here as well.

    """

    def __init__(self):
        self._pools = {
            pool: _PoolCounts() for pool in _MANAGED_POOLS
        }

    def record_host(self, host_history):
        """Add one `HostJobHistory` object to the collection.

        @param host_history The `HostJobHistory` object to be
                            remembered.

        """
        pool = host_history.host_pool
        self._pools[pool].record_host(host_history)


    def _count_pool(self, get_pool_count, pool=None):
        """Internal helper to count hosts in a given pool.

        The `get_pool_count` parameter is a function to calculate
        the exact count of interest for the pool.

        @param get_pool_count  Function to return a count from a
                               _PoolCount object.
        @param pool            The pool to be counted.  If `None`,
                               return the total across all pools.

        """
        if pool is None:
            return sum([get_pool_count(counts)
                            for counts in self._pools.values()])
        else:
            return get_pool_count(self._pools[pool])


    def get_working(self, pool=None):
        """Return the number of working DUTs in a pool.

        @param pool  The pool to be counted.  If `None`, return the
                     total across all pools.

        """
        return self._count_pool(_PoolCounts.get_working, pool)


    def get_broken(self, pool=None):
        """Return the number of broken DUTs in a pool.

        @param pool  The pool to be counted.  If `None`, return the
                     total across all pools.

        """
        return self._count_pool(_PoolCounts.get_broken, pool)


    def get_total(self, pool=None):
        """Return the total number of DUTs in a pool.

        @param pool  The pool to be counted.  If `None`, return the
                     total across all pools.

        """
        return self._count_pool(_PoolCounts.get_total, pool)


class _LabInventory(dict):
    """Collection of `HostJobHistory` objects for the Lab's inventory.

    The collection is indexed by board.  Indexing returns the
    _BoardCounts object associated with the board.

    The collection is also iterable.  The iterator returns all the
    boards in the inventory, in unspecified order.

    """

    @classmethod
    def create_inventory(cls, afe, start_time, end_time, boardlist=[]):
        """Return a Lab inventory with specified parameters.

        By default, gathers inventory from `HostJobHistory` objects
        for all DUTs in the `_MANAGED_POOLS` list.  If `boardlist`
        is supplied, the inventory will be restricted to only the
        given boards.

        @param afe         AFE object for constructing the
                           `HostJobHistory` objects.
        @param start_time  Start time for the `HostJobHistory`
                           objects.
        @param end_time    End time for the `HostJobHistory`
                           objects.
        @param boardlist   List of boards to include.  If empty,
                           include all available boards.
        @return A `_LabInventory` object for the specified boards.

        """
        label_list = [constants.Labels.POOL_PREFIX + l
                          for l in _MANAGED_POOLS]
        afehosts = afe.get_hosts(labels__name__in=label_list)
        if boardlist:
            boardhosts = []
            for board in boardlist:
                board_label = constants.Labels.BOARD_PREFIX + board
                host_list = [h for h in afehosts
                                  if board_label in h.labels]
                boardhosts.extend(host_list)
            afehosts = boardhosts
        create = lambda host: (
                status_history.HostJobHistory(afe, host,
                                              start_time, end_time))
        return cls([create(host) for host in afehosts])


    def __init__(self, histories):
        # N.B. The query that finds our hosts is restricted to those
        # with a valid pool: label, but doesn't check for a valid
        # board: label.  In some (insufficiently) rare cases, the
        # AFE hosts table has been known to (incorrectly) have DUTs
        # with a pool: but no board: label.  We explicitly exclude
        # those here.
        histories = [h for h in histories
                     if h.host_board is not None]
        boards = set([h.host_board for h in histories])
        initval = { board: _BoardCounts() for board in boards }
        super(_LabInventory, self).__init__(initval)
        self._dut_count = len(histories)
        for h in histories:
            self[h.host_board].record_host(h)


    def get_num_duts(self):
        """Return the total number of DUTs in the inventory."""
        return self._dut_count


    def get_num_boards(self):
        """Return the total number of boards in the inventory."""
        return len(self)


def _generate_board_inventory_message(inventory):
    """Generate the "board inventory" e-mail message.

    The board inventory is a list by board summarizing the number
    of working and broken DUTs, and the total shortfall or surplus
    of working devices relative to the minimum critical pool
    requirement.

    The report omits boards with no DUTs in the spare pool or with
    no DUTs in a critical pool.

    N.B. For sample output text formattted as users can expect to
    see it in e-mail and log files, refer to the unit tests.

    @param inventory  _LabInventory object with the inventory to
                      be reported on.
    @return String with the inventory message to be sent.

    """
    logging.debug('Creating board inventory')
    message = []
    message.append(
        '%-20s   %5s %5s %5s %5s %5s' % (
            'Board', 'Avail', 'Bad', 'Good', 'Spare', 'Total'))
    data_list = []
    for board, counts in inventory.items():
        logging.debug('Counting inventory for %s', board)
        spares = counts.get_total(_SPARE_POOL)
        total = counts.get_total()
        if spares == 0 or spares == total:
            continue
        working = counts.get_working()
        broken = counts.get_broken()
        buffer = spares - broken
        data_list.append((board, buffer, broken, working, spares, total))
    data_list = sorted(sorted(data_list, key=lambda t: -t[2]),
                       key=lambda t: t[1])
    message.extend(
            ['%-20s   %5d %5d %5d %5d %5d' % t for t in data_list])
    return '\n'.join(message)


_POOL_INVENTORY_HEADER = '''\
Notice to Infrastructure deputy:  If there are shortages below,
please take action to resolve them.  If it's safe, you should
balance shortages by running `balance_pool`.  Detailed instructions
can be found here:
    http://go/cros-manage-duts
'''


def _generate_pool_inventory_message(inventory):
    """Generate the "pool inventory" e-mail message.

    The pool inventory is a list by pool and board summarizing the
    number of working and broken DUTs in the pool.  Only boards with
    at least one broken DUT are included in the list.

    N.B. For sample output text formattted as users can expect to
    see it in e-mail and log files, refer to the unit tests.

    @param inventory  _LabInventory object with the inventory to
                      be reported on.
    @return String with the inventory message to be sent.

    """
    logging.debug('Creating pool inventory')
    message = [_POOL_INVENTORY_HEADER]
    newline = ''
    for pool in _CRITICAL_POOLS:
        message.append(
            '%sStatus for pool:%s, by board:' % (newline, pool))
        message.append(
            '%-20s   %5s %5s %5s' % (
                'Board', 'Bad', 'Good', 'Total'))
        data_list = []
        for board, counts in inventory.items():
            logging.debug('Counting inventory for %s, %s',
                          board, pool)
            broken = counts.get_broken(pool)
            if broken == 0:
                continue
            working = counts.get_working(pool)
            total = counts.get_total(pool)
            data_list.append((board, broken, working, total))
        if data_list:
            data_list = sorted(data_list, key=lambda d: -d[1])
            message.extend(
                ['%-20s   %5d %5d %5d' % t for t in data_list])
        else:
            message.append('(All boards at full strength)')
        newline = '\n'
    return '\n'.join(message)


def _send_email(arguments, tag, subject, recipients, body):
    """Send an inventory e-mail message.

    The message is logged in the selected log directory using `tag`
    for the file name.

    If the --print option was requested, the message is neither
    logged nor sent, but merely printed on stdout.

    @param arguments   Parsed command-line options.
    @param tag         Tag identifying the inventory for logging
                       purposes.
    @param subject     E-mail Subject: header line.
    @param recipients  E-mail addresses for the To: header line.
    @param body        E-mail message body.

    """
    logging.debug('Generating email: "%s"', subject)
    all_recipients = ', '.join(recipients)
    report_body = '\n'.join([
            'To: %s' % all_recipients,
            'Subject: %s' % subject,
            '', body, ''])
    if arguments.print_:
        print report_body
    else:
        filename = os.path.join(arguments.logdir, tag)
        try:
            report_file = open(filename, 'w')
            report_file.write(report_body)
            report_file.close()
        except EnvironmentError as e:
            logging.error('Failed to write %s:  %s', filename, e)
        try:
            gmail_lib.send_email(all_recipients, subject, body)
        except Exception as e:
            logging.error('Failed to send e-mail to %s:  %s',
                          all_recipients, e)


def _separate_email_addresses(address_list):
    """Parse a list of comma-separated lists of e-mail addresses.

    @param address_list  A list of strings containing comma
                         separate e-mail addresses.
    @return A list of the individual e-mail addresses.

    """
    newlist = []
    for arg in address_list:
        newlist.extend([email.strip() for email in arg.split(',')])
    return newlist


def _verify_arguments(arguments):
    """Validate command-line arguments.

    Join comma separated e-mail addresses for `--board-notify` and
    `--pool-notify` in separate option arguments into a single list.

    @param arguments  Command-line arguments as returned by
                      `ArgumentParser`

    """
    arguments.board_notify = _separate_email_addresses(
            arguments.board_notify)
    arguments.pool_notify = _separate_email_addresses(
            arguments.pool_notify)


def _get_logdir(script):
    """Get the default directory for the `--logdir` option.

    The default log directory is based on the parent directory
    containing this script.

    @param script  Path to this script file.
    @return A path to a directory.

    """
    basedir = os.path.dirname(os.path.abspath(script))
    basedir = os.path.dirname(basedir)
    return os.path.join(basedir, _LOGDIR)


def _parse_command(argv):
    """Parse the command line arguments.

    Create an argument parser for this command's syntax, parse the
    command line, and return the result of the ArgumentParser
    parse_args() method.

    @param argv Standard command line argument vector; argv[0] is
                assumed to be the command name.
    @return Result returned by ArgumentParser.parse_args().

    """
    parser = argparse.ArgumentParser(
            prog=argv[0],
            description='Gather and report lab inventory statistics')
    parser.add_argument('-d', '--duration', type=int,
                        default=_DEFAULT_DURATION, metavar='HOURS',
                        help='number of hours back to search for status'
                             ' (default: %d)' % _DEFAULT_DURATION)
    parser.add_argument('--board-notify', action='append',
                        default=[], metavar='ADDRESS',
                        help='Generate board inventory message, '
                        'and send it to the given e-mail address(es)')
    parser.add_argument('--pool-notify', action='append',
                        default=[], metavar='ADDRESS',
                        help='Generate pool inventory message, '
                             'and send it to the given address(es)')
    parser.add_argument('--print', dest='print_', action='store_true',
                        help='Print e-mail messages on stdout '
                             'without sending them.')
    parser.add_argument('--logdir', default=_get_logdir(argv[0]),
                        help='Directory where logs will be written.')
    parser.add_argument('boardnames', nargs='*',
                        metavar='BOARD',
                        help='names of boards to report on '
                             '(default: all boards)')
    arguments = parser.parse_args(argv[1:])
    _verify_arguments(arguments)
    return arguments


def _configure_logging(arguments):
    """Configure the `logging` module for our needs.

    How we log depends on whether the `--print` option was
    provided on the command line.  Without the option, we log all
    messages at DEBUG level or above, and write them to a file in
    the directory specified by the `--logdir` option.  With the
    option, we write log messages to stdout; messages below INFO
    level are discarded.

    The log file is configured to rotate once a week on Friday
    evening, preserving ~3 months worth of history.

    @param arguments  Command-line arguments as returned by
                      `ArgumentParser`

    """
    if arguments.print_:
        logging.getLogger().setLevel(logging.INFO)
        handler = logging.StreamHandler(sys.stdout)
        handler.setFormatter(logging.Formatter())
    else:
        logging.getLogger().setLevel(logging.DEBUG)
        logfile = os.path.join(arguments.logdir, _LOGFILE)
        handler = logging.handlers.TimedRotatingFileHandler(
                logfile, when='W4', backupCount=13)
        formatter = logging.Formatter(_LOG_FORMAT,
                                      time_utils.TIME_FMT)
        handler.setFormatter(formatter)
    logging.getLogger().addHandler(handler)


def _populate_board_counts(inventory):
    """Gather board counts while providing interactive feedback.

    Gathering the status of all individual DUTs in the lab can take
    considerable time (~30 minutes at the time of this writing).

    Normally, we pay that cost by querying as we go.  However, with
    the `--print` option, a human being may be watching the
    progress.  So, we force the first (expensive) queries to happen
    up front, and provide a small ASCII progress bar to give an
    indicator of how many boards have been processed.

    @param inventory  _LabInventory object with the inventory to
                      be gathered.

    """
    n = 0
    for counts in inventory.values():
        n += 1
        if n % 10 == 5:
            c = '+'
        elif n % 10 == 0:
            c = '%d' % ((n / 10) % 10)
        else:
            c = '.'
        sys.stdout.write(c)
        sys.stdout.flush()
        # This next call is where all the time goes - it forces all
        # of a board's HostJobHistory objects to query the database
        # and cache their results.
        counts.get_working()
    sys.stdout.write('\n')


def main(argv):
    """Standard main routine.
    @param argv  Command line arguments including `sys.argv[0]`.
    """
    arguments = _parse_command(argv)
    _configure_logging(arguments)
    try:
        end_time = int(time.time())
        start_time = end_time - arguments.duration * 60 * 60
        timestamp = time.strftime('%Y-%m-%d.%H',
                                  time.localtime(end_time))
        logging.debug('Starting lab inventory for %s', timestamp)
        if arguments.board_notify:
            logging.debug('Will include board inventory')
        if arguments.pool_notify:
            logging.debug('Will include pool inventory')

        afe = frontend.AFE(server=None)
        inventory = _LabInventory.create_inventory(
                afe, start_time, end_time, arguments.boardnames)
        logging.info('Found %d hosts across %d boards',
                         inventory.get_num_duts(),
                         inventory.get_num_boards())

        if arguments.print_:
            _populate_board_counts(inventory)

        if arguments.print_ or arguments.board_notify:
            _send_email(arguments,
                        'boards-%s.txt' % timestamp,
                        'DUT board inventory %s' % timestamp,
                        arguments.board_notify,
                        _generate_board_inventory_message(inventory))

        if arguments.print_ or arguments.pool_notify:
            _send_email(arguments,
                        'pools-%s.txt' % timestamp,
                        'DUT pool inventory %s' % timestamp,
                        arguments.pool_notify,
                        _generate_pool_inventory_message(inventory))
    except KeyboardInterrupt:
        pass
    except EnvironmentError as e:
        logging.exception('Unexpected OS error: %s', e)
    except Exception as e:
        logging.exception('Unexpected exception: %s', e)


if __name__ == '__main__':
    main(sys.argv)
