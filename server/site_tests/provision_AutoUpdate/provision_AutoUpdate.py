# Copyright (c) 2013 The Chromium OS Authors. All rights reserved.
# Use of this source code is governed by a BSD-style license that can be
# found in the LICENSE file.

import logging

from autotest_lib.client.common_lib import error
from autotest_lib.client.common_lib import global_config
from autotest_lib.client.common_lib.cros import dev_server
from autotest_lib.frontend.afe.json_rpc import proxy
from autotest_lib.server import frontend
from autotest_lib.server import test


_CONFIG = global_config.global_config
# pylint: disable-msg=E1120
_IMAGE_URL_PATTERN = _CONFIG.get_config_value(
        'CROS', 'image_url_pattern', type=str)
_CHROMEOS_VERSION_PREFIX = 'cros-version:'


# This has been copied out of dynamic_suite's reimager.py, which will be killed
# off in a future CL.  See the TODO below about how to get rid of this.
def _ensure_version_label(name):
    """
    Ensure that a label called exists in the autotest DB.

    @param name: the label to check for/create.
    """
    afe = frontend.AFE()
    try:
        afe.create_label(name=name)
    except proxy.ValidationError as ve:
        if ('name' in ve.problem_keys and
            'This value must be unique' in ve.problem_keys['name']):
            logging.debug('Version label %s already exists', name)
        else:
            raise ve


class provision_AutoUpdate(test.test):
    """A test that can provision a machine to the correct ChromeOS version."""
    version = 1

    def run_once(self, host, value):
        """The method called by the control file to start the test.

        @param host: The host object to update to |value|.
        @param value: The build type and version to install on the host.

        """
        image = value

        # If the host is already on the correct build, we have nothing to do.
        # Note that this means we're not doing any sort of stateful-only
        # update, and that we're relying more on cleanup to do cleanup.
        # We could just not pass |force_update=True| to |machine_install|,
        # but I'd like the semantics that a provision test 'returns' TestNA
        # if the machine is already properly provisioned.
        if host.get_build() == value:
            raise error.TestNAError('Host already running %s' % value)

        # We're about to reimage a machine, so we need full_payload and
        # stateful.  If something happened where the devserver doesn't have one
        # of these, then it's also likely that it'll be missing autotest.
        # Therefore, we require the devserver to also have autotest staged, so
        # that the test that runs after this provision finishes doesn't error
        # out because the devserver that its job_repo_url is set to is missing
        # autotest test code.
        # TODO(milleral): http://crbug.com/249426
        # Add an asynchronous staging call so that we can ask the devserver to
        # fetch autotest in the background here, and then wait on it after
        # reimaging finishes or at some other point in the provisioning.
        try:
            ds = dev_server.ImageServer.resolve(image)
            ds.stage_artifacts(image, ['full_payload', 'stateful', 'autotest'])
        except dev_server.DevServerException as e:
            raise error.TestFail(str(e))

        url = _IMAGE_URL_PATTERN % (ds.url(), image)

        # Installing a build on a host assumes that a label of
        # 'cros-version:<build>' has already been created, so we need to make
        # sure that one exists.
        # TODO(milleral):  http://crbug.com/249424
        # Consider making the add-a-label-to-a-host call automatically create a
        # label if it does not already exist.
        _ensure_version_label(_CHROMEOS_VERSION_PREFIX + image)

        try:
            host.machine_install(force_update=True, update_url=url)
        except error.InstallError as e:
            logging.error(e)
            raise error.TestFail(str(e))
