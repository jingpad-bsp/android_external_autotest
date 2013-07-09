# Copyright (c) 2012 The Chromium OS Authors. All rights reserved.
# Use of this source code is governed by a BSD-style license that can be
# found in the LICENSE file.

import os

import common

from autotest_lib.client.common_lib.cros.site_wlan import constants
from autotest_lib.client.cros import constants as cros_constants
from autotest_lib.server.cros.wlan import api_shim


class ProfileManager(api_shim.ApiShim):
    """Context manager that allows for manipulation of Shill profiles.

    Only supports creation/deletion at this time.
    Currently implemented in terms of flimflam test scripts.

    This API should evolve together with the refactor of the tools in
    client/common_lib/cros/site_wlan to provide an RPC interface to
    drive connectivity on DUTs: http://crosbug.com/35757
    """

    _TEST_PROFILE_NAME = 'test'

    def __init__(self, host):
        super(ProfileManager, self).__init__(host)
        self._pop_profile = os.path.join(self._script, 'profile pop')
        self._rm_profile = os.path.join(self._script, 'profile remove')
        self._push_profile = os.path.join(self._script, 'profile push')
        self._create_profile = os.path.join(self._script, 'profile create')


    def __enter__(self):
        """Ensures a testing global profile exists."""
        self._remove_test_global_profile(ignore_status=True)
        self._create_test_global_profile()
        return self


    def __exit__(self, exntype, exnvalue, backtrace):
        """Removes the testing global profile.

        @raise CmdError: a helper command failed while removing the profile.
        """
        self._remove_test_global_profile()


    def _build_script_path(self, host):
        """Returns fully-specified path to wrapped script directory.

        @param host: a hosts.Host object pointed at the DUT.

        @return fully-specified path to the wrapped script.
        """
        end = cros_constants.FLIMFLAM_TEST_PATH.lstrip('/')
        # I wish I had a better way than hard-coding /usr/local here.
        # TODO(quiche?): http://crosbug.com/36132
        return os.path.join('/usr/local', end)


    def _remove_test_global_profile(self, ignore_status=False):
        """Attempts to remove (testing) global shill profile.

        @param ignore_status: do not raise an exception, no matter what the exit
            code of the command is.

        @raise CmdError: a helper command failed while removing the profile.
        """
        self._client.run('%s %s' % (self._pop_profile,
                                    self._TEST_PROFILE_NAME),
                         ignore_status=ignore_status)
        self._client.run('%s %s' % (self._rm_profile,
                                    self._TEST_PROFILE_NAME),
                         ignore_status=ignore_status)


    def _create_test_global_profile(self, ignore_status=False):
        """Attempts to create (testing) global shill profile.

        @param ignore_status: do not raise an exception, no matter what the exit
            code of the command is.

        @raise CmdError: a helper command failed while making the profile.
        """
        self._client.run('%s %s' % (self._create_profile,
                                    self._TEST_PROFILE_NAME),
                         ignore_status=ignore_status)
        self._client.run('%s %s' % (self._push_profile,
                                    self._TEST_PROFILE_NAME),
                         ignore_status=ignore_status)


    def remove_user_profile(self, ignore_status=False):
        """Removes user-specific shill profile.

        There will be no user-specific profile upon success.

        @param ignore_status: do not raise an exception, no matter what the exit
            code of the command is.

        @raise CmdError: a helper command failed while removing the profile.
        """
        self._client.run('%s %s' % (self._pop_profile,
                                    constants.USER_PROFILE_NAME),
                         ignore_status=ignore_status)
        self._client.run('%s %s' % (self._rm_profile,
                                    constants.USER_PROFILE_NAME),
                         ignore_status=ignore_status)


    def clear_global_profile(self, ignore_status=False):
        """Ensure existence of a clear (testing) global shill profile.

        Remove any existing global profile and create a clean one.

        @param ignore_status: do not raise an exception, no matter what the exit
            code of the command is.

        @raise CmdError: a helper command failed while deleting or creating
                         the profile.
        """
        self._remove_test_global_profile(ignore_status=ignore_status)
        self._create_test_global_profile(ignore_status=ignore_status)
