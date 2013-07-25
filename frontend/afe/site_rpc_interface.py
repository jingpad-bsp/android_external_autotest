# pylint: disable-msg=C0111

# Copyright (c) 2012 The Chromium OS Authors. All rights reserved.
# Use of this source code is governed by a BSD-style license that can be
# found in the LICENSE file.

__author__ = 'cmasone@chromium.org (Chris Masone)'

import common
import datetime
import logging

from autotest_lib.client.common_lib import error
from autotest_lib.client.common_lib import priorities
from autotest_lib.client.common_lib.cros import dev_server
from autotest_lib.server.cros.dynamic_suite import constants
from autotest_lib.server.cros.dynamic_suite import control_file_getter
from autotest_lib.server.cros.dynamic_suite import job_status
from autotest_lib.server.cros.dynamic_suite import tools
from autotest_lib.site_utils.graphite import stats


# Relevant CrosDynamicSuiteExceptions are defined in client/common_lib/error.py.


def _rpc_utils():
    """Returns the rpc_utils module.  MUST be mocked for unit tests.

    rpc_utils initializes django, which we can't do in unit tests.
    This layer of indirection allows us to only load that module if we're
    not running unit tests.

    @return: autotest_lib.frontend.afe.rpc_utils
    """
    from autotest_lib.frontend.afe import rpc_utils
    return rpc_utils


def canonicalize_suite_name(suite_name):
    return 'test_suites/control.%s' % suite_name


def formatted_now():
    return datetime.datetime.now().strftime(job_status.TIME_FMT)


def get_control_file_contents_by_name(build, board, ds, suite_name):
    """Return control file contents for |suite_name|.

    Query the dev server at |ds| for the control file |suite_name|, included
    in |build| for |board|.

    @param build: unique name by which to refer to the image from now on.
    @param board: the kind of device to run the tests on.
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
        raise type(e)("%s while testing %s for %s." % (e, build, board))
    if not control_file_in:
        raise error.ControlFileEmpty(
                "Fetching %s returned no data." % suite_name)
    # Force control files to only contain ascii characters.
    try:
        control_file_in.encode('ascii')
    except UnicodeDecodeError as e:
        raise error.ControlFileMalformed(str(e))

    return control_file_in


def create_suite_job(suite_name, board, build, pool, check_hosts=True,
                     num=None, file_bugs=False, timeout=24,
                     priority=priorities.Priority.DEFAULT,
                     suite_args=None):
    """
    Create a job to run a test suite on the given device with the given image.

    When the timeout specified in the control file is reached, the
    job is guaranteed to have completed and results will be available.

    @param suite_name: the test suite to run, e.g. 'bvt'.
    @param board: the kind of device to run the tests on.
    @param build: unique name by which to refer to the image from now on.
    @param pool: Specify the pool of machines to use for scheduling
            purposes.
    @param check_hosts: require appropriate live hosts to exist in the lab.
    @param num: Specify the number of machines to schedule across (integer).
                Leave unspecified or use None to use default sharding factor.
    @param file_bugs: File a bug on each test failure in this suite.
    @param timeout: The max lifetime of this suite, in hours.
    @param priority: Integer denoting priority. Higher is more important.
    @param suite_args: Optional arguments which will be parsed by the suite
                       control file. Used by control.test_that_wrapper to
                       determine which tests to run.

    @raises ControlFileNotFound: if a unique suite control file doesn't exist.
    @raises NoControlFileList: if we can't list the control files at all.
    @raises StageBuildFailure: if the dev server throws 500 while staging build.
    @raises ControlFileEmpty: if the control file exists on the server, but
                              can't be read.

    @return: the job ID of the suite; -1 on error.
    """
    stats.Counter('create_suite_job').increment()
    # All suite names are assumed under test_suites/control.XX.
    suite_name = canonicalize_suite_name(suite_name)
    if type(num) is not int and num is not None:
        raise error.SuiteArgumentException('Ill specified num argument %r. '
                                           'Must be an integer or None.' % num)
    if num == 0:
        logging.warning("Can't run on 0 hosts; using default.")
        num = None

    timings = {}
    # Ensure components of |build| necessary for installing images are staged
    # on the dev server. However set synchronous to False to allow other
    # components to be downloaded in the background.
    ds = dev_server.ImageServer.resolve(build)
    timings[constants.DOWNLOAD_STARTED_TIME] = formatted_now()
    try:
        ds.trigger_download(build, synchronous=False)
    except dev_server.DevServerException as e:
        raise error.StageBuildFailure(
                "Failed to stage %s for %s: %s" % (build, board, e))
    timings[constants.PAYLOAD_FINISHED_TIME] = formatted_now()

    control_file_in = get_control_file_contents_by_name(build, board, ds,
                                                        suite_name)


    # prepend build and board to the control file
    inject_dict = {'board': board,
                   'build': build,
                   'check_hosts': check_hosts,
                   'pool': pool,
                   'num': num,
                   'file_bugs': file_bugs,
                   'timeout': timeout,
                   'devserver_url': ds.url(),
                   'priority': priority,
                   'suite_args' : suite_args
                   }

    control_file = tools.inject_vars(inject_dict, control_file_in)

    return _rpc_utils().create_job_common('%s-%s' % (build, suite_name),
                                          priority=priority,
                                          timeout=timeout,
                                          max_runtime_mins=timeout*60,
                                          control_type='Server',
                                          control_file=control_file,
                                          hostless=True,
                                          keyvals=timings)
