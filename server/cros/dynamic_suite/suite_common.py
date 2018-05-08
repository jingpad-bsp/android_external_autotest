# Copyright 2018 The Chromium OS Authors. All rights reserved.
# Use of this source code is governed by a BSD-style license that can be
# found in the LICENSE file.

"""Shared functions by dynamic_suite/suite.py & skylab_suite/cros_suite.py."""

from __future__ import division
from __future__ import print_function

import datetime
import re

import common

from autotest_lib.client.common_lib import error
from autotest_lib.client.common_lib import time_utils
from autotest_lib.client.common_lib.cros import dev_server
from autotest_lib.server.cros import provision
from autotest_lib.server.cros.dynamic_suite import constants


def _formatted_now():
    """Format the current datetime."""
    return datetime.datetime.now().strftime(time_utils.TIME_FMT)


def make_builds_from_options(options):
    """Create a dict of builds for creating a suite job.

    The returned dict maps version label prefixes to build names. Together,
    each key-value pair describes a complete label.

    @param options: SimpleNamespace from argument parsing.

    @return: dict mapping version label prefixes to build names
    """
    builds = {}
    build_prefix = None
    if options.build:
        build_prefix = provision.get_version_label_prefix(options.build)
        builds[build_prefix] = options.build

    if options.cheets_build:
        builds[provision.CROS_ANDROID_VERSION_PREFIX] = options.cheets_build
        if build_prefix == provision.CROS_VERSION_PREFIX:
            builds[build_prefix] += provision.CHEETS_SUFFIX

    if options.firmware_rw_build:
        builds[provision.FW_RW_VERSION_PREFIX] = options.firmware_rw_build

    if options.firmware_ro_build:
        builds[provision.FW_RO_VERSION_PREFIX] = options.firmware_ro_build

    return builds


def get_test_source_build(builds, **dargs):
    """Get the build of test code.

    Get the test source build from arguments. If parameter
    `test_source_build` is set and has a value, return its value. Otherwise
    returns the ChromeOS build name if it exists. If ChromeOS build is not
    specified either, raise SuiteArgumentException.

    @param builds: the builds on which we're running this suite. It's a
                   dictionary of version_prefix:build.
    @param **dargs: Any other Suite constructor parameters, as described
                    in Suite.__init__ docstring.

    @return: The build contains the test code.
    @raise: SuiteArgumentException if both test_source_build and ChromeOS
            build are not specified.

    """
    if dargs.get('test_source_build', None):
        return dargs['test_source_build']

    cros_build = builds.get(provision.CROS_VERSION_PREFIX, None)
    if cros_build.endswith(provision.CHEETS_SUFFIX):
        test_source_build = re.sub(
                provision.CHEETS_SUFFIX + '$', '', cros_build)
    else:
        test_source_build = cros_build

    if not test_source_build:
        raise error.SuiteArgumentException(
                'test_source_build must be specified if CrOS build is not '
                'specified.')

    return test_source_build


def stage_build_artifacts(build, hostname=None):
    """
    Ensure components of |build| necessary for installing images are staged.

    @param build image we want to stage.
    @param hostname hostname of a dut may run test on. This is to help to locate
        a devserver closer to duts if needed. Default is None.

    @raises StageControlFileFailure: if the dev server throws 500 while staging
        suite control files.

    @return: dev_server.ImageServer instance to use with this build.
    @return: timings dictionary containing staging start/end times.
    """
    timings = {}
    # Ensure components of |build| necessary for installing images are staged
    # on the dev server. However set synchronous to False to allow other
    # components to be downloaded in the background.
    ds = dev_server.resolve(build, hostname=hostname)
    ds_name = ds.hostname
    timings[constants.DOWNLOAD_STARTED_TIME] = _formatted_now()
    try:
        ds.stage_artifacts(image=build, artifacts=['test_suites'])
    except dev_server.DevServerException as e:
        raise error.StageControlFileFailure(
                "Failed to stage %s on %s: %s" % (build, ds_name, e))
    timings[constants.PAYLOAD_FINISHED_TIME] = _formatted_now()
    return ds, timings
