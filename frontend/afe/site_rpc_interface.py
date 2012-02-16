# Copyright (c) 2012 The Chromium OS Authors. All rights reserved.
# Use of this source code is governed by a BSD-style license that can be
# found in the LICENSE file.

__author__ = 'cmasone@chromium.org (Chris Masone)'

import common
import logging
import sys
from autotest_lib.client.common_lib import global_config
from autotest_lib.client.common_lib.cros import dev_server
# rpc_utils initializes django, which we can't do in unit tests.
if 'unittest' not in sys.modules.keys():
    # So, only load that module if we're not running unit tests.
    from autotest_lib.frontend.afe import rpc_utils
from autotest_lib.server.cros import control_file_getter, dynamic_suite


class StageBuildFailure(Exception):
    """Raised when the dev server throws 500 while staging a build."""
    pass


class ControlFileEmpty(Exception):
    """Raised when the control file exists on the server, but can't be read."""
    pass


def _rpc_utils():
    """Returns the rpc_utils module.  MUST be mocked for unit tests."""
    return rpc_utils


def create_suite_job(suite_name, board, build, pool):
    """
    Create a job to run a test suite on the given device with the given image.

    When the timeout specified in the control file is reached, the
    job is guaranteed to have completed and results will be available.

    @param suite_name: the test suite to run, e.g. 'bvt'.
    @param board: the kind of device to run the tests on.
    @param build: unique name by which to refer to the image from now on.
    @param pool: Specify the pool of machines to use for scheduling
            purposes.

    @throws ControlFileNotFound if a unique suite control file doesn't exist.
    @throws NoControlFileList if we can't list the control files at all.
    @throws StageBuildFailure if the dev server throws 500 while staging build.
    @throws ControlFileEmpty if the control file exists on the server, but
                             can't be read.

    @return: the job ID of the suite; -1 on error.
    """
    # All suite names are assumed under test_suites/control.XX.
    suite_name = 'test_suites/control.%s' % suite_name
    # Ensure |build| is staged is on the dev server.
    ds = dev_server.DevServer.create()
    if not ds.trigger_download(build):
        raise StageBuildFailure("Server error while staging " + build)

    getter = control_file_getter.DevServerGetter.create(build, ds)
    # Get the control file for the suite.
    control_file_in = getter.get_control_file_contents_by_name(suite_name)
    if not control_file_in:
        raise ControlFileEmpty("Fetching %s returned no data." % suite_name)

    # prepend build and board to the control file
    inject_dict = {'board': board,
                   'build': build,
                   'pool': pool}
    control_file = dynamic_suite.inject_vars(inject_dict, control_file_in)

    return _rpc_utils().create_job_common('%s-%s' % (build, suite_name),
                                          priority='Medium',
                                          control_type='Server',
                                          control_file=control_file,
                                          hostless=True)
