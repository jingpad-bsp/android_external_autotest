# Copyright (c) 2013 The Chromium OS Authors. All rights reserved.
# Use of this source code is governed by a BSD-style license that can be
# found in the LICENSE file.

import os, sys

from autotest_lib.client.bin import test, utils
from autotest_lib.client.common_lib import error
from autotest_lib.client.common_lib.cros import chrome, session_manager
from autotest_lib.client.cros import constants, login, ownership


class login_OwnershipTaken(test.test):
    """Sign in and ensure that ownership of the device is taken."""
    version = 1


    def setup(self):
        os.chdir(self.srcdir)
        utils.make('OUT_DIR=.')


    def initialize(self):
        ownership.restart_ui_to_clear_ownership_files()
        if (os.access(constants.OWNER_KEY_FILE, os.F_OK) or
            os.access(constants.SIGNED_POLICY_FILE, os.F_OK)):
            raise error.TestError('Ownership already taken!')


    def _validate_policy(self, retrieved_policy, username):
        # Pull in protobuf definitions.
        sys.path.append(self.srcdir)
        from chrome_device_policy_pb2 import ChromeDeviceSettingsProto
        from chrome_device_policy_pb2 import UserWhitelistProto
        from device_management_backend_pb2 import PolicyData
        from device_management_backend_pb2 import PolicyFetchResponse

        response_proto = PolicyFetchResponse()
        response_proto.ParseFromString(retrieved_policy)
        ownership.assert_has_policy_data(response_proto)

        poldata = PolicyData()
        poldata.ParseFromString(response_proto.policy_data)
        ownership.assert_has_device_settings(poldata)
        ownership.assert_username(poldata, username)

        polval = ChromeDeviceSettingsProto()
        polval.ParseFromString(poldata.policy_value)
        ownership.assert_new_users(polval, True)
        ownership.assert_users_on_whitelist(polval, (username,))


    def run_once(self):
        with chrome.Chrome() as cr:
            login.wait_for_ownership()

            sm = session_manager.connect()
            retrieved_policy = sm.RetrievePolicy(byte_arrays=True)
            if retrieved_policy is None:
                raise error.TestFail('Policy not found.')
            self._validate_policy(retrieved_policy, cr.username)
