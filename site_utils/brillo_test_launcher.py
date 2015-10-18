#!/usr/bin/python
# Copyright 2015 The Chromium OS Authors. All rights reserved.
# Use of this source code is governed by a BSD-style license that can be
# found in the LICENSE file.

import argparse
import httplib
import logging
import os
import sys
import tempfile
import time
import urllib2

import common
try:
    # Ensure the chromite site-package is installed.
    from chromite.lib import *
except ImportError:
    import subprocess
    build_externals_path = os.path.join(
            os.path.dirname(os.path.dirname(os.path.realpath(__file__))),
            'utils', 'build_externals.py')
    subprocess.check_call([build_externals_path, 'chromiterepo'])
    # Restart the script so python now finds the autotest site-packages.
    sys.exit(os.execv(__file__, sys.argv))
from autotest_lib.client.common_lib import control_data
from autotest_lib.client.common_lib import error
from autotest_lib.server import hosts
from autotest_lib.server import utils
from autotest_lib.server.hosts import moblab_host
from autotest_lib.server.cros.dynamic_suite import control_file_getter
from autotest_lib.server.cros.dynamic_suite import tools
from autotest_lib.site_utils import run_suite


LOGGING_FORMAT = '%(asctime)s - %(levelname)s - %(message)s'
MOBLAB_STATIC_DIR = '/mnt/moblab/static'
MOBLAB_TMP_DIR = os.path.join(MOBLAB_STATIC_DIR, 'tmp')
TARGET_IMAGE_NAME = 'brillo/target'
DEVSERVER_STAGE_URL_TEMPLATE = ('http://%(moblab)s:%(port)s/stage?local_path='
                                '%(staged_dir)s&artifacts=full_payload')
AFE_JOB_PAGE_TEMPLATE = ('http://%(moblab)s/afe/#tab_id=view_job&object_id='
                         '%(job_id)s')
AFE_HOST_PAGE_TEMPLATE = ('http://%(moblab)s/afe/#tab_id=view_host&object_id='
                          '%(host_id)s')

# Running against a virtual machine has several intricacies that we need to
# adjust for. Namely SSH requires the use of 'localhost' while HTTP requires
# the use of '127.0.0.1'. Also because we are forwarding the ports from the VM
# to the host system, the ports to use for these services are also different
# from running on a physical machine.
VIRT_MACHINE_SSH_ADDR = 'localhost:9222'
VIRT_MACHINE_AFE_ADDR = '127.0.0.1:8888'
VIRT_MACHINE_DEVSERVER_PORT = '7777'
PHYS_MACHINE_DEVSERVER_PORT = '8888'
QUICKMERGE_LIST = ['client/',
                   'global_config.ini',
                   'server/',
                   'site_utils/',
                   'test_suites/',
                   'utils/']


class BrilloTestError(Exception):
    """A general error during test invocation."""


class PayloadStagingError(BrilloTestError):
    """A failure that occurred while staging an update payload."""


def parse_args():
    """Parse command line arguments"""
    parser = argparse.ArgumentParser()
    parser.add_argument('-d', '--debug', action='store_true',
                        help='Print log statements.')
    parser.add_argument('-q', '--quickmerge', action='store_true',
                        help='Rsync over modified Autotest code.')
    parser.add_argument('-p', '--payload',
                        help='Path to the update payload for autoupdate '
                             'testing.')
    parser.add_argument('-t', '--test_name',
                        help="Name of the test to run. This is either the "
                             "name in the test's default control file e.g. "
                             "brillo_Gtests or a specific control file's "
                             "filename e.g. control.brillo_GtestsWhitelist.")
    parser.add_argument('-A', '--test_arg', metavar='NAME=VAL',
                        dest='test_args', default=[], action='append',
                        help='An argument to pass to the test.')
    parser.add_argument('-m', '--moblab_host',
                        help='MobLab hostname or IP to launch tests. If this '
                             'argument is not provided, the test launcher '
                             'will attempt to test a local virtual machine '
                             'instance of MobLab.')
    parser.add_argument('-v', '--virtual_machine', action='store_true',
                        help='MobLab is running locally on a virtual machine.')
    parser.add_argument('-a', '--adb_host',
                        help='Hostname or IP of the adb_host connected to the '
                             'Brillo DUT. Default is to assume it is connected '
                             'directly to the MobLab.')

    return parser.parse_args()


def add_adbhost(moblab, adb_hostname):
    """Add the ADB host to the MobLab's host list.

    @param moblab: MoblabHost representing the MobLab being used to launch the
                   tests.
    @param adb_hostname: Hostname of the ADB Host.

    @returns The adb host to use for launching tests.
    """
    if not adb_hostname:
        adb_hostname = 'localhost'
        moblab.enable_adb_testing()
    if all([host.hostname != adb_hostname for host in moblab.afe.get_hosts()]):
        moblab.add_dut(adb_hostname)
    return adb_hostname


def stage_payload(moblab, payload, vm):
    """Stage the payload on the MobLab.

    # TODO (sbasi): Add support to stage source payloads.

    @param moblab: MoblabHost representing the MobLab being used to launch the
                   testing.
    @param payload: Path to the Brillo payload that will be staged.
    @param vm: Boolean if True means we are running in a VM.

    @raise PayloadStagingError: If we failed to stage the payload.
    """
    if not os.path.exists(payload):
        raise PayloadStagingError('Payload file %s does not exist.' % payload)
    stage_tmp_dir = os.path.join(MOBLAB_TMP_DIR, TARGET_IMAGE_NAME)
    stage_dest_dir = os.path.join(MOBLAB_STATIC_DIR, TARGET_IMAGE_NAME)
    stage_tmp_file = os.path.join(stage_tmp_dir, 'target_full_.bin')
    moblab.run('mkdir -p %s' % stage_tmp_dir)
    moblab.send_file(payload, stage_tmp_file)
    moblab.run('chown -R moblab:moblab %s' % MOBLAB_TMP_DIR)
    # Remove any artifacts that were previously staged.
    moblab.run('rm -rf %s' % stage_dest_dir)
    port = VIRT_MACHINE_DEVSERVER_PORT if vm else PHYS_MACHINE_DEVSERVER_PORT
    try:
        stage_url = DEVSERVER_STAGE_URL_TEMPLATE % dict(
                moblab=moblab.web_address,
                port=port,
                staged_dir=stage_tmp_dir)
        res = urllib2.urlopen(stage_url).read()
    except (urllib2.HTTPError, httplib.HTTPException, urllib2.URLError) as e:
        raise PayloadStagingError('Unable to stage payload on moblab: %s' % e)
    else:
        if res == 'Success':
            logging.debug('Payload is staged on Moblab as %s',
                          TARGET_IMAGE_NAME)
        else:
            raise PayloadStagingError('Staging failed: %s' % res)
    finally:
        moblab.run('rm -rf %s' % stage_tmp_dir)


def schedule_test(moblab, host, test, test_args):
    """Schedule a Brillo test.

    @param moblab: MoblabHost representing the MobLab being used to launch the
                   testing.
    @param host: Hostname of the DUT.
    @param test: Test name.
    @param test_args: Iterable of 'NAME=VAL' (strings) encoding argument
                      assignments for the test.

    @returns autotest_lib.server.frontend.Job object representing the scheduled
             job.
    """
    getter = control_file_getter.FileSystemGetter(
            [os.path.dirname(os.path.dirname(os.path.realpath(__file__)))])
    controlfile_conts = getter.get_control_file_contents_by_name(test)

    # TODO(garnold) This should be removed and arguments injected by feeding
    # args=test_args to create_jobs() directly once crbug.com/545572 is fixed.
    if test_args:
        controlfile_conts = tools.inject_vars({'args': test_args},
                                              controlfile_conts)

    job = moblab.afe.create_job(
            controlfile_conts, name=test,
            control_type=control_data.CONTROL_TYPE_NAMES.SERVER,
            hosts=[host], require_ssp=False)
    logging.info('Tests Scheduled. Please wait for results.')
    job_page = AFE_JOB_PAGE_TEMPLATE % dict(moblab=moblab.web_address,
                                            job_id=job.id)
    logging.info('Progress can be monitored at %s', job_page)
    logging.info('Please note tests that launch other tests (e.g. sequences) '
                 'might complete quickly, but links to child jobs will appear '
                 'shortly at the bottom on the page (Hit Refresh).')
    return job


def get_all_jobs(moblab, parent_job):
    """Generate a list of the parent_job and it's subjobs.

    @param moblab: MoblabHost representing the MobLab being used to launch the
                   testing.
    @param host: Hostname of the DUT.
    @param parent_job: autotest_lib.server.frontend.Job object representing the
                       parent job.

    @returns list of autotest_lib.server.frontend.Job objects.
    """
    jobs_list = moblab.afe.get_jobs(id=parent_job.id)
    jobs_list.extend(moblab.afe.get_jobs(parent_job=parent_job.id))
    return jobs_list


def wait_for_test_completion(moblab, host, parent_job):
    """Wait for the parent job and it's subjobs to complete.

    @param moblab: MoblabHost representing the MobLab being used to launch the
                   testing.
    @param host: Hostname of the DUT.
    @param parent_job: autotest_lib.server.frontend.Job object representing the
                       test job.
    """
    # Wait for the sequence job and it's sub-jobs to finish, while monitoring
    # the DUT state. As long as the DUT does not go into 'Repair Failed' the
    # tests will complete.
    while (moblab.afe.get_jobs(id=parent_job.id, not_yet_run=True,
                               running=True)
           or moblab.afe.get_jobs(parent_job=parent_job.id, not_yet_run=True,
                                  running=True)):
        afe_host = moblab.afe.get_hosts(hostnames=(host,))[0]
        if afe_host.status == 'Repair Failed':
            moblab.afe.abort_jobs(
                [j.id for j in get_all_jobs(moblab, parent_job)])
            host_page = AFE_HOST_PAGE_TEMPLATE % dict(
                    moblab=moblab.web_address, host_id=afe_host.id)
            raise BrilloTestError(
                    'ADB dut %s has become Repair Failed. More information '
                    'can be found at %s' % (host, host_page))
        time.sleep(10)


def output_results(moblab, parent_job):
    """Output the Brillo PTS and it's subjobs results.

    @param moblab: MoblabHost representing the MobLab being used to launch the
                   testing.
    @param parent_job: autotest_lib.server.frontend.Job object representing the
                       test job.
    """
    solo_test_run = len(moblab.afe.get_jobs(parent_job=parent_job.id)) == 0
    rc = run_suite.ResultCollector(moblab.web_address, moblab.afe, moblab.tko,
                                   None, None, parent_job.name, parent_job.id,
                                   user='moblab', solo_test_run=solo_test_run)
    rc.run()
    rc.output_results()


def copy_results(moblab, parent_job):
    """Copy job results locally.

    @param moblab: MoblabHost representing the MobLab being used to launch the
                   testing.
    @param parent_job: autotest_lib.server.frontend.Job object representing the
                       parent job.

    @returns Temporary directory path.
    """
    tempdir = tempfile.mkdtemp(prefix='brillo_test_results')
    for job in get_all_jobs(moblab, parent_job):
        moblab.get_file('/usr/local/autotest/results/%d-moblab' % job.id,
                        tempdir)
    return tempdir


def setup_moblab_host(args):
    """Setup the MobLab Host Object.

    @params args: argparse.Namespace object representing the parsed args.

    @returns Tuple of (moblab_host.MoblabHost, boolean indicating if the
                       MobLab is running in a virtual machine).

    @raise BrilloTestError: An error occurred while setting up the Moblab.
    """
    is_vm = False
    web_address = args.moblab_host
    if not args.moblab_host:
        logging.info('MobLab host name was not provided. Attempting to '
                     'launch the test against a local virtual machine.')
        is_vm = True
        args.moblab_host = VIRT_MACHINE_SSH_ADDR
        web_address = VIRT_MACHINE_AFE_ADDR
    # Create a MoblabHost to interact with the Moblab device.
    try:
        moblab = hosts.create_host(args.moblab_host,
                                   host_class=moblab_host.MoblabHost,
                                   web_address=web_address)
    except error.AutoservRunError as e:
        raise BrilloTestError('Unable to connect to the MobLab: %s' % e)

    try:
        moblab.afe.get_hosts()
    except Exception as e:
        raise BrilloTestError(
                "Unable to communicate with the MobLab's web frontend, "
                "please verify that it is up and running at http://%s/\n"
                "Error: %s" % (moblab.web_address, e))
    return (moblab, is_vm)


def quickmerge(moblab):
    """Transfer over a subset of Autotest directories.

    Quickmerge allows developers to do basic editting of tests and test
    libraries on their workstation without requiring them to emerge and cros
    deploy the autotest-server package.

    @param moblab: MoblabHost representing the MobLab being used to launch the
                   testing.
    """
    autotest_rootdir = os.path.dirname(
            os.path.dirname(os.path.realpath(__file__)))
    for item in QUICKMERGE_LIST:
        src = os.path.join(autotest_rootdir,item)
        dest = ':'.join(['moblab@%s' % moblab.hostname,
                         os.path.join(moblab_host.AUTOTEST_INSTALL_DIR, item)])
        rsync_cmd = ['rsync', '-a', '--exclude', '*.pyc', src, dest]
        utils.run(' '.join(rsync_cmd), timeout=120)


def main(args):
    """The main function."""
    args = parse_args()
    level = logging.DEBUG if args.debug else logging.INFO
    # Without a full site-packages, logging's root log handler needs to be
    # manually setup.
    logger = logging.getLogger()
    for handler in logger.handlers:
        logger.removeHandler(handler)
    logger.setLevel(level)
    handler = logging.StreamHandler()
    handler.setFormatter(logging.Formatter(LOGGING_FORMAT))
    logger.addHandler(handler)

    moblab, is_vm = setup_moblab_host(args)

    if args.quickmerge:
        quickmerge(moblab)

    # Add the adb host object to the MobLab.
    adb_host = add_adbhost(moblab, args.adb_host)

    # Stage the payload if provided.
    if args.payload:
        stage_payload(moblab, args.payload, is_vm)

    # Schedule the test job.
    test_job = schedule_test(moblab, adb_host, args.test_name, args.test_args)
    wait_for_test_completion(moblab, adb_host, test_job)

    # Gather and report the test results.
    local_results_folder = copy_results(moblab, test_job)
    output_results(moblab, test_job)
    logging.info('Results have also been copied locally to %s',
                 local_results_folder)


if __name__ == '__main__':
    try:
        main(sys.argv)
        sys.exit(0)
    except BrilloTestError as e:
        logging.error('Error: %s', e)

    sys.exit(1)
