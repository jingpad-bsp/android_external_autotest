# Copyright (c) 2012 The Chromium OS Authors. All rights reserved.
# Use of this source code is governed by a BSD-style license that can be
# found in the LICENSE file.

__author__ = 'cmasone@chromium.org (Chris Masone)'

import common
import datetime
import logging
import sys
from autotest_lib.client.common_lib import error, global_config
from autotest_lib.client.common_lib.cros import dev_server
from autotest_lib.server.cros import control_file_getter, dynamic_suite


# Relevant CrosDynamicSuiteExceptions are defined in client/common_lib/error.py.


class ControlFileEmpty(Exception):
    """Raised when the control file exists on the server, but can't be read."""
    pass


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


def create_suite_job(suite_name, board, build, pool, check_hosts=True):
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

    @raises ControlFileNotFound if a unique suite control file doesn't exist.
    @raises NoControlFileList if we can't list the control files at all.
    @raises StageBuildFailure if the dev server throws 500 while staging build.
    @raises ControlFileEmpty if the control file exists on the server, but
                             can't be read.

    @return: the job ID of the suite; -1 on error.
    """
    # All suite names are assumed under test_suites/control.XX.
    suite_name = canonicalize_suite_name(suite_name)

    timings = {}
    time_fmt = '%Y-%m-%d %H:%M:%S'
    # Ensure components of |build| necessary for installing images are staged
    # on the dev server. However set synchronous to False to allow other
    # components to be downloaded in the background.
    ds = dev_server.DevServer.create()
    timings['download_started_time'] = datetime.datetime.now().strftime(
        time_fmt)
    if not ds.trigger_download(build, synchronous=False):
        raise error.StageBuildFailure("Server error while staging " + build)
    timings['payload_finished_time'] = datetime.datetime.now().strftime(
        time_fmt)

    getter = control_file_getter.DevServerGetter.create(build, ds)
    # Get the control file for the suite.
    control_file_in = getter.get_control_file_contents_by_name(suite_name)
    if not control_file_in:
        raise error.ControlFileEmpty(
            "Fetching %s returned no data." % suite_name)

    # prepend build and board to the control file
    inject_dict = {'board': board,
                   'build': build,
                   'check_hosts': check_hosts,
                   'pool': pool}
    control_file = dynamic_suite.inject_vars(inject_dict, control_file_in)

    return _rpc_utils().create_job_common('%s-%s' % (build, suite_name),
                                          priority='Medium',
                                          control_type='Server',
                                          control_file=control_file,
                                          hostless=True,
                                          keyvals=timings)
