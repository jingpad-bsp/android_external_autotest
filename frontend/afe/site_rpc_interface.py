# pylint: disable-msg=C0111

# Copyright (c) 2012 The Chromium OS Authors. All rights reserved.
# Use of this source code is governed by a BSD-style license that can be
# found in the LICENSE file.

__author__ = 'cmasone@chromium.org (Chris Masone)'

import common
import datetime
import logging
import os
import shutil
import utils

from autotest_lib.client.common_lib import error
from autotest_lib.client.common_lib import global_config
from autotest_lib.client.common_lib import priorities
from autotest_lib.client.common_lib.cros import dev_server
from autotest_lib.frontend.afe import rpc_utils
from autotest_lib.server import utils
from autotest_lib.server.cros.dynamic_suite import constants
from autotest_lib.server.cros.dynamic_suite import control_file_getter
from autotest_lib.server.cros.dynamic_suite import job_status
from autotest_lib.server.cros.dynamic_suite import tools
from autotest_lib.server.hosts import moblab_host


_CONFIG = global_config.global_config
MOBLAB_BOTO_LOCATION = '/home/moblab/.boto'


# Relevant CrosDynamicSuiteExceptions are defined in client/common_lib/error.py.


def canonicalize_suite_name(suite_name):
    return 'test_suites/control.%s' % suite_name


def formatted_now():
    return datetime.datetime.now().strftime(job_status.TIME_FMT)


def _get_control_file_contents_by_name(build, ds, suite_name):
    """Return control file contents for |suite_name|.

    Query the dev server at |ds| for the control file |suite_name|, included
    in |build| for |board|.

    @param build: unique name by which to refer to the image from now on.
    @param ds: a dev_server.DevServer instance to fetch control file with.
    @param suite_name: canonicalized suite name, e.g. test_suites/control.bvt.
    @raises ControlFileNotFound if a unique suite control file doesn't exist.
    @raises NoControlFileList if we can't list the control files at all.
    @raises ControlFileEmpty if the control file exists on the server, but
                             can't be read.

    @return the contents of the desired control file.
    """
    getter = control_file_getter.DevServerGetter.create(build, ds)
    # Get the control file for the suite.
    try:
        control_file_in = getter.get_control_file_contents_by_name(suite_name)
    except error.CrosDynamicSuiteException as e:
        raise type(e)("%s while testing %s." % (e, build))
    if not control_file_in:
        raise error.ControlFileEmpty(
                "Fetching %s returned no data." % suite_name)
    # Force control files to only contain ascii characters.
    try:
        control_file_in.encode('ascii')
    except UnicodeDecodeError as e:
        raise error.ControlFileMalformed(str(e))

    return control_file_in


def _stage_build_artifacts(build):
    """
    Ensure components of |build| necessary for installing images are staged.

    @param build image we want to stage.

    @raises StageBuildFailure: if the dev server throws 500 while staging
        build.

    @return: dev_server.ImageServer instance to use with this build.
    @return: timings dictionary containing staging start/end times.
    """
    timings = {}
    # Set synchronous to False to allow other components to be downloaded in
    # the background.
    ds = dev_server.ImageServer.resolve(build)
    timings[constants.DOWNLOAD_STARTED_TIME] = formatted_now()
    try:
        ds.stage_artifacts(build, ['test_suites'])
    except dev_server.DevServerException as e:
        raise error.StageBuildFailure(
                "Failed to stage %s: %s" % (build, e))
    timings[constants.PAYLOAD_FINISHED_TIME] = formatted_now()
    return (ds, timings)


def create_suite_job(name='', board='', build='', pool='', control_file='',
                     check_hosts=True, num=None, file_bugs=False, timeout=24,
                     timeout_mins=None, priority=priorities.Priority.DEFAULT,
                     suite_args=None, wait_for_results=True, job_retry=False,
                     **kwargs):
    """
    Create a job to run a test suite on the given device with the given image.

    When the timeout specified in the control file is reached, the
    job is guaranteed to have completed and results will be available.

    @param name: The test name if control_file is supplied, otherwise the name
                 of the test suite to run, e.g. 'bvt'.
    @param board: the kind of device to run the tests on.
    @param build: unique name by which to refer to the image from now on.
    @param pool: Specify the pool of machines to use for scheduling
            purposes.
    @param check_hosts: require appropriate live hosts to exist in the lab.
    @param num: Specify the number of machines to schedule across (integer).
                Leave unspecified or use None to use default sharding factor.
    @param file_bugs: File a bug on each test failure in this suite.
    @param timeout: The max lifetime of this suite, in hours.
    @param timeout_mins: The max lifetime of this suite, in minutes. Takes
                         priority over timeout.
    @param priority: Integer denoting priority. Higher is more important.
    @param suite_args: Optional arguments which will be parsed by the suite
                       control file. Used by control.test_that_wrapper to
                       determine which tests to run.
    @param wait_for_results: Set to False to run the suite job without waiting
                             for test jobs to finish. Default is True.
    @param job_retry: Set to True to enable job-level retry. Default is False.
    @param kwargs: extra keyword args. NOT USED.

    @raises ControlFileNotFound: if a unique suite control file doesn't exist.
    @raises NoControlFileList: if we can't list the control files at all.
    @raises StageBuildFailure: if the dev server throws 500 while staging build.
    @raises ControlFileEmpty: if the control file exists on the server, but
                              can't be read.

    @return: the job ID of the suite; -1 on error.
    """
    if type(num) is not int and num is not None:
        raise error.SuiteArgumentException('Ill specified num argument %r. '
                                           'Must be an integer or None.' % num)
    if num == 0:
        logging.warning("Can't run on 0 hosts; using default.")
        num = None

    (ds, timings) = _stage_build_artifacts(build)

    if not control_file:
      # No control file was supplied so look it up from the build artifacts.
      suite_name = canonicalize_suite_name(name)
      control_file = _get_control_file_contents_by_name(build, ds, suite_name)
      name = '%s-%s' % (build, suite_name)

    timeout_mins = timeout_mins or timeout * 60

    if not board:
        board = utils.ParseBuildName(build)[0]

    # Prepend build and board to the control file.
    inject_dict = {'board': board,
                   'build': build,
                   'check_hosts': check_hosts,
                   'pool': pool,
                   'num': num,
                   'file_bugs': file_bugs,
                   'timeout': timeout,
                   'timeout_mins': timeout_mins,
                   'devserver_url': ds.url(),
                   'priority': priority,
                   'suite_args' : suite_args,
                   'wait_for_results': wait_for_results,
                   'job_retry': job_retry
                   }

    control_file = tools.inject_vars(inject_dict, control_file)

    return rpc_utils.create_job_common(name,
                                          priority=priority,
                                          timeout_mins=timeout_mins,
                                          max_runtime_mins=timeout*60,
                                          control_type='Server',
                                          control_file=control_file,
                                          hostless=True,
                                          keyvals=timings)


# TODO: hide the following rpcs under is_moblab
def moblab_only(func):
    """Ensure moblab specific functions only run on Moblab devices."""
    def verify(*args, **kwargs):
        if not utils.is_moblab():
            raise error.RPCException('RPC: %s can only run on Moblab Systems!',
                                     func.__name__)
        return func(*args, **kwargs)
    return verify


@moblab_only
def get_config_values():
    """Returns all config values parsed from global and shadow configs.

    Config values are grouped by sections, and each section is composed of
    a list of name value pairs.
    """
    sections =_CONFIG.get_sections()
    config_values = {}
    for section in sections:
        config_values[section] = _CONFIG.config.items(section)
    return rpc_utils.prepare_for_serialization(config_values)


@moblab_only
def update_config_handler(config_values):
    """
    Update config values and override shadow config.

    @param config_values: See get_moblab_settings().
    """
    for section, config_value_list in config_values.iteritems():
        for key, value in config_value_list:
            _CONFIG.override_config_value(section, key, value)
    if not _CONFIG.shadow_file or not os.path.exists(_CONFIG.shadow_file):
        raise error.RPCException('Shadow config file does not exist.')

    with open(_CONFIG.shadow_file, 'w') as config_file:
        _CONFIG.config.write(config_file)
    # TODO (sbasi) crbug.com/403916 - Remove the reboot command and
    # instead restart the services that rely on the config values.
    os.system('sudo reboot')


@moblab_only
def reset_config_settings():
    with open(_CONFIG.shadow_file, 'w') as config_file:
      pass
    os.system('sudo reboot')


@moblab_only
def set_boto_key(boto_key):
    """Update the boto_key file.

    @param boto_key: File name of boto_key uploaded through handle_file_upload.
    """
    if not os.path.exists(boto_key):
        raise error.RPCException('Boto key: %s does not exist!' % boto_key)
    shutil.copyfile(boto_key, moblab_host.MOBLAB_BOTO_LOCATION)
