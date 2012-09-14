# Copyright (c) 2012 The Chromium OS Authors. All rights reserved.
# Use of this source code is governed by a BSD-style license that can be
# found in the LICENSE file.

from autotest_lib.client.cros import chrome_test


class enterprise_DevicePolicy(chrome_test.PyAutoFunctionalTest):
    version = 1


    def run_once(self):
        tests = [
            # TODO(nirnimesh): Stuck at 'pick user iamge' screen after login.
            # crbug.com/149126
            # 'testGuestModeEnabled',
            # 'testUserWhitelistInAccountPicker',
            'testShowUserNamesOnSignin',
            'testTimezoneSettingWithoutPolicy',
            'testTimezoneSettingWithPolicy',

            # testUserWhitelistAndAllowNewUsers is broken
            # crosbug.com/33435
        ]
        tests = ['chromeos_device_policy.ChromeosDevicePolicy.' + x
                 for x in tests]
        self.run_pyauto_functional(tests=tests)
