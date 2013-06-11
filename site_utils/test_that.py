#!/usr/bin/python
# Copyright (c) 2013 The Chromium OS Authors. All rights reserved.
# Use of this source code is governed by a BSD-style license that can be
# found in the LICENSE file.

import argparse
import logging
import os
import re
import subprocess
import sys
import tempfile

import common
from autotest_lib.client.common_lib.cros import dev_server
from autotest_lib.server.cros.dynamic_suite import suite
from autotest_lib.server.cros.dynamic_suite import constants
from autotest_lib.server import autoserv_utils

try:
    from chromite.lib import cros_build_lib
except ImportError:
    print 'Unable to import chromite.'
    print 'This script must be either:'
    print '  - Be run in the chroot.'
    print '  - (not yet supported) be run after running '
    print '    ../utils/build_externals.py'


def schedule_local_suite(autotest_path, suite_name, afe, build=''):
    """
    Schedule a suite against a mock afe object, for a local suite run.
    @param autotest_path: Absolute path to autotest (in sysroot).
    @param suite_name: Name of suite to schedule.
    @param afe: afe object to schedule against (typically a directAFE)
    @param build: Build to schedule suite for.
    """
    fs_getter = suite.Suite.create_fs_getter(autotest_path)
    devserver = dev_server.ImageServer('')
    my_suite = suite.Suite.create_from_name(suite_name, build, devserver,
                                            fs_getter, afe, ignore_deps=True)
    if len(my_suite.tests) == 0:
        raise ValueError('Suite named %s does not exist, or contains no '
                         'tests.' % suite_name)
    my_suite.schedule(lambda x: None) # Schedule tests, discard record calls.


def schedule_local_test(autotest_path, suite_name, afe, build=''):
    #temporarily disabling pylint
    #pylint: disable-msg=C0111
    """
    Schedule an individual test against a mock afe object, for a local run.

    NOT YET IMPLEMENTED
    """
    pass


def run_job(job, host, sysroot_autotest_path):
    """
    Shell out to autoserv to run an individual test job.

    @param job: A Job object containing the control file contents and other
                relevent metadata for this test.
    @param host: Hostname of DUT to run test against.
    @param sysroot_autotest_path: Absolute path of autotest directory.
    """
    with tempfile.NamedTemporaryFile() as temp_file:
        temp_file.write(job.control_file)
        temp_file.flush()

        command = autoserv_utils.autoserv_run_job_command(
                os.path.join(sysroot_autotest_path, 'server'),
                machines=host, job=job, verbose=False,
                extra_args=[temp_file.name])
        subprocess.call(command)


def setup_local_afe():
    """
    Setup a local afe database and return a direct_afe object to access it.

    @returns: A autotest_lib.frontend.afe.direct_afe instance.
    """
    # This import statement is delayed until now rather than running at
    # module load time, because it kicks off a local sqlite :memory: backed
    # database, and we don't need that unless we are doing a local run.
    from autotest_lib.frontend import setup_django_lite_environment
    from autotest_lib.frontend.afe import direct_afe
    return direct_afe.directAFE()


def perform_local_run(afe, autotest_path, tests, remote, build=''):
    """
    @param afe: A direct_afe object used to interact with local afe database.
    @param autotest_path: Absolute path of sysroot installed autotest.
    @param tests: List of strings naming tests and suites to run. Suite strings
                  should be formed like "suite:smoke".
    @param remote: Remote hostname.
    @param build: String specifying build for local run.
    """
    afe.create_label(constants.VERSION_PREFIX + build)
    afe.create_host(remote)

    # Schedule tests / suites in local afe
    for test in tests:
        suitematch = re.match(r'suite:(.*)', test)
        if suitematch:
            suitename = suitematch.group(1)
            logging.info('Scheduling suite %s.', suitename)
            schedule_local_suite(autotest_path, suitename, afe)
        else:
            logging.info('Would schedule test %s.', test)

    for job in afe.get_jobs():
        run_job(job, remote, autotest_path)

    return 0


def validate_arguments(arguments):
    """
    Validates parsed arguments.

    @param arguments: arguments object, as parsed by ParseArguments
    @raises: ValueError if arguments were invalid.
    """
    if arguments.args:
        raise ValueError('--args flag not yet supported.')

    if not arguments.board:
        raise ValueError('Board autodetection not yet supported. '
                         '--board required.')

    if arguments.remote == ':lab:':
        raise ValueError('Running tests in test lab not yet supported.')


def parse_arguments(argv):
    """
    Parse command line arguments

    @param argv: argument list to parse
    @returns:    parsed arguments.
    """
    parser = argparse.ArgumentParser(description='Run remote tests.')

    parser.add_argument('remote', metavar='REMOTE',
                        help='hostname[:port] for remote device. Specify '
                        ':lab: to run in test lab, or :vm:PORT_NUMBER to '
                        'run in vm.')
    parser.add_argument('tests', nargs='+', metavar='TEST',
                        help='Run given test(s). Use suite:SUITE to specify '
                        'test suite.')
    parser.add_argument('-b', '--board', metavar='BOARD',
                        action='store',
                        help='Board for which the test will run.')
    parser.add_argument('-i', '--build', metavar='BUILD',
                        help='Build to test. Device will be reimaged if '
                        'necessary. Omit flag to skip reimage and test '
                        'against already installed DUT image.')
    parser.add_argument('--args', metavar='ARGS',
                        help='Argument string to pass through to test.')

    return parser.parse_args(argv)


def main(argv):
    """
    Entry point for test_that script.
    @param argv: arguments list
    """
    if not cros_build_lib.IsInsideChroot():
        logging.error('Script must be invoked inside the chroot.')
        return 1

    logging.getLogger('').setLevel(logging.INFO)

    arguments = parse_arguments(argv)
    try:
        validate_arguments(arguments)
    except ValueError as err:
        logging.error('Invalid arguments. %s', err.message)
        return 1

    # TODO: Determine the following string programatically.
    # (same TODO applied to autotest_quickmerge)
    sysroot_path = os.path.join('/build', arguments.board, '')
    sysroot_autotest_path = os.path.join(sysroot_path, 'usr', 'local',
                                         'autotest', '')
    sysroot_site_utils_path = os.path.join(sysroot_autotest_path,
                                            'site_utils')

    if not os.path.exists(sysroot_path):
        logging.error('%s does not exist. Have you run setup_board?',
                      sysroot_path)
        return 1
    if not os.path.exists(sysroot_autotest_path):
        logging.error('%s does not exist. Have you run build_packages?',
                      sysroot_autotest_path)
        return 1

    # If we are not running the sysroot version of script, re-execute
    # that version of script with the same arguments.
    realpath = os.path.realpath(__file__)
    if os.path.dirname(realpath) != sysroot_site_utils_path:
        script_command = os.path.join(sysroot_site_utils_path,
                                      os.path.basename(realpath))
        return subprocess.call([script_command] + argv)

    # Hard coded to True temporarily. This will eventually be parsed to false
    # if we are doing a run in the test lab.
    local_run = True

    if local_run:
        afe = setup_local_afe()
        return perform_local_run(afe, sysroot_autotest_path, arguments.tests,
                               arguments.remote)

if __name__ == '__main__':
    sys.exit(main(sys.argv[1:]))
