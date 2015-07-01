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
from autotest_lib.site_utils.deployment import commandline
from autotest_lib.site_utils.suite_scheduler import constants


_LOG_FORMAT = '%(asctime)s | %(levelname)-10s | %(message)s'

_DEFAULT_POOL = constants.Labels.POOL_PREFIX + 'suites'


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
    # There's a time delay between completion of `start servod` and
    # and servod actually being up and serving, so add a delay to
    # make sure the verify() call doesn't fail.
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
    if hostlist:
        afe_host = hostlist[0]
        if not afe_host.locked or afe_host.status != 'Ready':
            return 'Host exists, but is not locked and idle'
    else:
        afe_host = None

    try:
        host = _create_host(hostname, arguments.board)
        _check_servo(host)
        host._servo_repair_reinstall()
    except error.AutoservRunError as re:
        logging.exception('Failed to install: %s', re)
        return 'chromeos-install failed'
    except Exception as e:
        logging.exception('Failed to install: %s', e)
        return str(e)
    finally:
        host.close()

    if afe_host is not None:
        try:
            logging.debug('Unlocking host in AFE.')
            afe_host.modify(locked=False, lock_reason='')
        except Exception as e:
            logging.exception('Failed to unlock: %s', e)
            return 'Failed to unlock after installing'
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
    afe_host = afe.get_hosts([hostname])[0]
    haveboard = False
    for label in afe_host.labels:
        if label.startswith(constants.Labels.BOARD_PREFIX):
            haveboard = True
            break
    if not haveboard:
        afe_host.delete()
        return 'Failed to add labels to host'
    return None


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
    results = install_pool.map(install_function, arguments.hostnames)
    successful = []
    for r, h in zip(results, arguments.hostnames):
        if r is None:
            successful.append(h)
        else:
            sys.stdout.write('%-30s %s\n' % (h, r))
    if successful:
        if successful == arguments.hostnames:
            sys.stdout.write('All hosts passed, scheduling verify.\n')
        else:
            sys.stdout.write('\nScheduling verify for successful hosts.\n')
        afe.reverify_hosts(hostnames=successful)
        for h in afe.get_hosts(hostnames=successful):
            havepool = False
            for label in h.labels:
                if label.startswith(constants.Labels.POOL_PREFIX):
                    sys.stdout.write('%-30s already in %s.\n' %
                                     (h.hostname, label))
                    havepool = True
                    break
            if not havepool:
                sys.stdout.write('%-30s adding to %s.\n' %
                                 (h.hostname, _DEFAULT_POOL))
                h.add_labels([_DEFAULT_POOL])
    else:
        sys.stdout.write('Installation failed for all DUTs.\n')

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
