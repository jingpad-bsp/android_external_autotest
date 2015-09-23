#!/usr/bin/env python
# Copyright 2015 The Chromium OS Authors. All rights reserved.
# Use of this source code is governed by a BSD-style license that can be
# found in the LICENSE file.

"""Install an initial test image on a set of DUTs.

The target DUTs are newly deployed, and are normally in a slightly
anomalous state:
  * The DUTs are running a production base image, not a test image.
    By extension, the DUTs aren't reachable over SSH.
  * The DUTs are not necessarily in the AFE database.  DUTs that
    _are_ in the database should be locked.  Either way, the DUTs
    cannot be scheduled to run tests.
  * The servos for the DUTs need not be configured with the proper
    board.

The script imposes these preconditions:
  * Every DUT has a properly connected servo.
  * Every DUT and servo has proper DHCP and DNS configurations.
  * Every servo host is up and running, and accessible via SSH.
  * There is a known, working test image that can be staged and
    installed on the target DUTs via servo.
  * Every DUT has the same board.

Installation is done using the standard servo repair process (that
is, boot and install a test image from USB).  The implementation
uses the `multiprocessing` module to run all installations in
parallel, separate processes.

"""

import functools
import logging
import multiprocessing
import os
import shutil
import subprocess
import sys
import tempfile
import time

import common
from autotest_lib.client.common_lib import error
from autotest_lib.client.common_lib import time_utils
from autotest_lib.server import frontend
from autotest_lib.server import hosts
from autotest_lib.server.cros.dynamic_suite.constants import VERSION_PREFIX
from autotest_lib.site_utils.deployment import commandline
from autotest_lib.site_utils.suite_scheduler.constants import Labels


_LOG_FORMAT = '%(asctime)s | %(levelname)-10s | %(message)s'

_DEFAULT_POOL = Labels.POOL_PREFIX + 'suites'

_DIVIDER = '\n============\n'


def _create_host(hostname, board):
    """Create a CrosHost object for a DUT to be installed.

    @param hostname  Hostname of the target DUT.
    @param board     Board name of the target DUT.
    """
    host = hosts.create_host(hostname, try_lab_servo=True)
    # Monkey patch our host object to think there's a board label
    # in the AFE.  The horror!  The horror!
    #
    # TODO(jrbarnette):  This is wrong; we patch the method because
    # CrosHost._servo_repair_reinstall() calls it, but that means
    # we're coupled to the implementation of CrosHost.  Alas, it's
    # hard to do better without either 1) copying large chunks of
    # _servo_repair_reinstall(), or 2) extensively refactoring
    # CrosHost.
    host._get_board_from_afe = lambda: board
    return host


def _check_servo(host):
    """Check that servo for the given host is working.

    Perform these steps:
      * Confirm that the servo host is reachable via SSH.
      * Stop `servod` on the servo host if it's running, and restart
        it with the host's designated board.  We deliberately ignore
        any prior configuration.
      * Re-verify that the servo service on the servo host is
        working correctly.
      * Re-initialize the DUT host object with the correct servo
        object, since this won't have been done in the case that
        `servod` was down.
      * Re-initialize the servo settings, since restarting `servod`
        can change the actual settings from the expected defaults.
        (In particular, restarting `servod` leaves the USB stick
        plugged in to the servo host.)

    @param host  CrosHost object with the servo to be initialized.
    """
    if not host._servo_host:
        raise Exception('No answer to ping from Servo host')
    if not host._servo_host.is_up():
        raise Exception('No answer to ssh from Servo host')
    # Stop servod, ignoring failures, then restart with the proper
    # board.
    #
    # There's a lag between when `start servod` completes and when
    # servod is actually up and serving.  The call to time.sleep()
    # below gives time to make sure that the verify() call won't
    # fail.
    host._servo_host.run('stop servod || :')
    host._servo_host.run('start servod BOARD=%s' %
                         host._get_board_from_afe())
    time.sleep(4)
    logging.debug('Starting servo host verification')
    host._servo_host.verify()
    host.servo = host._servo_host.get_servo()
    host.servo.initialize_dut()
    if not host.servo.probe_host_usb_dev():
        raise Exception('No USB stick detected on Servo host')


def _configure_install_logging():
    """Configure the logging module for `_install_dut()`."""
    handler = logging.StreamHandler(sys.stderr)
    formatter = logging.Formatter(_LOG_FORMAT, time_utils.TIME_FMT)
    handler.setFormatter(formatter)
    root_logger = logging.getLogger()
    for h in root_logger.handlers:
        root_logger.removeHandler(h)
    root_logger.addHandler(handler)


def _try_lock_host(afe_host):
    """Lock a host in the AFE, and report whether it succeeded.

    The lock action is logged regardless of success; failures are
    logged if they occur.

    @param afe_host AFE Host instance to be locked.
    @return `True` on success, or `False` on failure.
    """
    try:
        logging.warning('Locking host now.')
        afe_host.modify(locked=True,
                        lock_reason='Running deployment_test')
    except Exception as e:
        logging.exception('Failed to lock: %s', e)
        return False
    return True


def _try_unlock_host(afe_host):
    """Unlock a host in the AFE, and report whether it succeeded.

    The unlock action is logged regardless of success; failures are
    logged if they occur.

    @param afe_host AFE Host instance to be unlocked.
    @return `True` on success, or `False` on failure.
    """
    try:
        logging.warning('Unlocking host.')
        afe_host.modify(locked=False, lock_reason='')
    except Exception as e:
        logging.exception('Failed to unlock: %s', e)
        return False
    return True


def _install_dut(arguments, hostname):
    """Install the initial test image on one DUT using servo.

    Implementation note: This function is expected to run in a
    subprocess created by a multiprocessing Pool object.  As such,
    it can't (shouldn't) write to shared files like `sys.stdout`.

    @param hostname   Host name of the DUT to install on.
    @param arguments  Parsed results from
                      ArgumentParser.parse_args().
    @return On success, return `None`.  On failure, return a string
            with an error message.
    """
    # In some cases, autotest code that we're calling below may put
    # stuff onto stdout with 'print' statements.  Most notably, the
    # AFE frontend may print 'FAILED RPC CALL' (boo, hiss).  We want
    # nothing from this subprocess going to the output we inherited
    # from our parent, so redirect stdout and stderr here, before
    # we make any AFE calls.  Note that this does what we want only
    # because we're in a subprocess.
    log_name = os.path.join(arguments.dir, hostname + '.log')
    sys.stdout = open(log_name, 'w')
    sys.stderr = sys.stdout
    _configure_install_logging()

    afe = frontend.AFE(server=arguments.web)
    hostlist = afe.get_hosts([hostname])
    unlock_on_failure = False
    if hostlist:
        afe_host = hostlist[0]
        if not afe_host.locked:
            if _try_lock_host(afe_host):
                unlock_on_failure = True
            else:
                return 'Failed to lock host'
        if (afe_host.status != 'Ready' and
                 afe_host.status != 'Repair Failed'):
            if unlock_on_failure and not _try_unlock_host(afe_host):
                return 'Host is in use, and failed to unlock it'
            return 'Host is in use by Autotest'
    else:
        afe_host = None

    try:
        host = _create_host(hostname, arguments.board)
        _check_servo(host)
        if not arguments.noinstall:
            host._servo_repair_reinstall()
    except error.AutoservRunError as re:
        logging.exception('Failed to install: %s', re)
        if unlock_on_failure and not _try_unlock_host(afe_host):
            logging.error('Failed to unlock host!')
        return 'chromeos-install failed'
    except Exception as e:
        logging.exception('Failed to install: %s', e)
        if unlock_on_failure and not _try_unlock_host(afe_host):
            logging.error('Failed to unlock host!')
        return str(e)
    finally:
        host.close()

    if afe_host is not None:
        if not _try_unlock_host(afe_host):
            return 'Failed to unlock after successful install'
    else:
        logging.debug('Creating host in AFE.')
        atest_path = os.path.join(
                os.path.dirname(os.path.abspath(sys.argv[0])),
                'atest')
        status = subprocess.call(
                [atest_path, 'host', 'create', hostname])
        if status != 0:
            logging.error('Host creation failed, status = %d', status)
            return 'Failed to add host to AFE'
    # Must re-query to get state changes, especially label changes.
    afe_host = afe.get_hosts([hostname])[0]
    have_board = any([label.startswith(Labels.BOARD_PREFIX)
                         for label in afe_host.labels])
    if not have_board:
        afe_host.delete()
        return 'Failed to add labels to host'
    version = [label for label in afe_host.labels
                   if label.startswith(VERSION_PREFIX)]
    if version:
        afe_host.remove_labels(version)
    return None


def _report_hosts(heading, host_results_list):
    """Report results for a list of hosts.

    To improve visibility, results are preceded by a header line,
    followed by a divider line.  Then results are printed, one host
    per line.

    @param heading            The header string to be printed before
                              results.
    @param host_results_list  A list of (hostname, message) tuples
                              to be printed one per line.
    """
    if not host_results_list:
        return
    sys.stdout.write(heading)
    sys.stdout.write(_DIVIDER)
    for t in host_results_list:
        sys.stdout.write('%-30s %s\n' % t)
    sys.stdout.write('\n')


def _report_results(afe, hostnames, results):
    """Gather and report a summary of results from installation.

    Segregate results into successes and failures, reporting
    each separately.  At the end, report the total of successes
    and failures.

    @param afe        AFE object for RPC calls.
    @param hostnames  List of the hostnames that were tested.
    @param results    List of error messages, in the same order
                      as the hostnames.  `None` means the
                      corresponding host succeeded.
    """
    success_hosts = []
    success_reports = []
    failure_reports = []
    for r, h in zip(results, hostnames):
        if r is None:
            success_hosts.append(h)
        else:
            failure_reports.append((h, r))
    if success_hosts:
        afe_host_list = afe.get_hosts(hostnames=success_hosts)
        afe.reverify_hosts(hostnames=success_hosts)
        for h in afe.get_hosts(hostnames=success_hosts):
            for label in h.labels:
                if label.startswith(Labels.POOL_PREFIX):
                    success_reports.append(
                            (h.hostname, 'Host already in %s' % label))
                    break
            else:
                h.add_labels([_DEFAULT_POOL])
                success_reports.append(
                        (h.hostname, 'Host added to %s' % _DEFAULT_POOL))
    sys.stdout.write(_DIVIDER)
    _report_hosts('Successes', success_reports)
    _report_hosts('Failures', failure_reports)
    sys.stdout.write('Installation complete:  '
                     '%d successes, %d failures.\n' %
                         (len(success_reports), len(failure_reports)))


def main(argv):
    """Standard main routine.

    @param argv  Command line arguments including `sys.argv[0]`.
    """
    # Override tempfile.tempdir.  Some of the autotest code we call
    # will create temporary files that don't get cleaned up.  So, we
    # put the temp files in our results directory, so that we can
    # clean up everything in one fell swoop.
    tempfile.tempdir = tempfile.mkdtemp()

    arguments = commandline.parse_command(argv)
    if not arguments:
        sys.exit(1)
    sys.stderr.write('Installation output logs in %s\n' % arguments.dir)
    afe = frontend.AFE(server=arguments.web)
    if arguments.build:
        afe.run('set_stable_version',
                version=arguments.build,
                board=arguments.board)
    install_pool = multiprocessing.Pool(len(arguments.hostnames))
    install_function = functools.partial(_install_dut, arguments)
    results_list = install_pool.map(install_function,
                                    arguments.hostnames)
    current_build = afe.run('get_stable_version',
                            board=arguments.board)
    sys.stderr.write('\nRepair version for board %s is now %s.\n' %
                         (arguments.board, current_build))
    _report_results(afe, arguments.hostnames, results_list)

    # MacDuff:
    #   [ ... ]
    #   Did you say all? O hell-kite! All?
    #   What, all my pretty chickens and their dam
    #   At one fell swoop?
    shutil.rmtree(tempfile.tempdir)


if __name__ == '__main__':
    try:
        main(sys.argv)
    except KeyboardInterrupt:
        pass
    except EnvironmentError as e:
        sys.stderr.write('Unexpected OS error:\n    %s\n' % e)
    except Exception as e:
        sys.stderr.write('Unexpected exception:\n    %s\n' % e)
