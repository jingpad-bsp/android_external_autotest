# Copyright (c) 2013 The Chromium OS Authors. All rights reserved.
# Use of this source code is governed by a BSD-style license that can be
# found in the LICENSE file.

# This file lets us test the repair supporting code.
# We could not easily unit test it if it was in the repair file as it makes
# a function call that is not protected by a __name__ == ??? guard.

import datetime, logging, operator, urllib2, xmlrpclib

import common

from autotest_lib.client.common_lib import logging_config
from autotest_lib.server import frontend

# Ignore any jobs that were ran more than this many hours ago.
_CUTOFF_HOURS = 24
LOGFILE_NAME = 'machine_death.log'


class MachineDeathLogger(logging_config.LoggingConfig):
    """
    Used to log information about a machine going into the Repair Failed state.

    We use this so that if the default log location ever changes it will also
    change for this logger and to keep this information separate from the
    other logs.

    """
    file_formatter = logging.Formatter(fmt='%(asctime)s | %(message)s',
                                       datefmt='%m/%d %H:%M:%S')

    def __init__(self):
        super(MachineDeathLogger, self).__init__(False)
        self.logger = logging.getLogger('machine_death')

        super(MachineDeathLogger, self).configure_logging(use_console=False)
        log_dir = self.get_server_log_dir()
        self.add_file_handler(LOGFILE_NAME, logging.ERROR, log_dir=log_dir)


def _find_problem_test(machine, rpc):
    """
    Finds the last job ran on a machine.

    @param machine: The hostname (e.g. IP address) of the machine to find the
        last ran job on it.

    @param rpc: The rpc object to contact the server with.

    @return the job status dictionary for the job that last ran on the machine
        or None if there is no such job.
    """
    # Going through the RPC interface means we cannot use the latest() django
    # QuerySet function. So we will instead look at the past 24 hours and
    # pick the most recent run from there.
    cutoff = (datetime.datetime.today() -
              datetime.timedelta(hours=_CUTOFF_HOURS))

    results = rpc.run('get_host_queue_entries', host__hostname=machine,
                      started_on__gte=str(cutoff))

    if results:
        return max(results, key=operator.itemgetter('started_on'))
    else:
        return None


def flag_problem_test(machine):
    """
    Notify people about the last job that ran on a machine.

    This code is ran when a machine goes into the Repair Failed state and so
    there is a chance that the last ran job on it killed it.

    This logs information to a special log file. We are doing this to
    check if keeping track of this information is actually useful.

    @param machine: The hostname (e.g. IP address) of the machine to find the
        last job ran on it.

    """
    logger = MachineDeathLogger()
    rpc = frontend.AFE()

    try:
        problem_test = _find_problem_test(machine, rpc)
        if problem_test:
            # We want the machine death information to be logged to a special
            # file but we do not want every other message to be logged to
            # that file.
            logger.logger.error('%s | %d | %s'
                                % (machine, problem_test['job']['id'],
                                   problem_test['job']['name']))
        else:
            logger.logger.error('%s | No job detected' % machine)

    except urllib2.URLError:
        logger.logger.error('%s | ERROR: Could not contact RPC server'
                            % machine)
    except xmlrpclib.ProtocolError as e:
        logger.logger.error('%s | ERROR: RPC Protocol Error: %s'
                            % (machine, e.errmsg))

