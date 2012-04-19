# Copyright (c) 2012 The Chromium OS Authors. All rights reserved.
# Use of this source code is governed by a BSD-style license that can be
# found in the LICENSE file.

import os

from autotest_lib.client.common_lib import error
from autotest_lib.client.cros import enterprise_ui_test


class desktopui_EnterprisePolicy(enterprise_ui_test.EnterpriseUITest):
    version = 1
    _POLICY_EXPECTED_FILE = os.path.join('chromeos', 'enterprise',
                                         'policies')


    def _compare_policies(self, expected_policy, actual_policy):
        """Compare two policy dictionaries.

        Args:
            expected_policy: A dictionary of expected policies.
            actual_policy: A dictionary of actual policies.

        Returns:
            String diff between the two dictionaries, None if identical.
        """
        expected_policy_set = set(expected_policy)
        actual_policy_set = set(actual_policy)
        diff = ''
        for missing_key in expected_policy_set - actual_policy_set:
            diff += ('Missing policy\n  %s\n' %
                     {missing_key: expected_policy[missing_key]})

        for extra_key in actual_policy_set - expected_policy_set:
            diff += ('Extra policy\n  %s\n' %
                     {extra_key: actual_policy[extra_key]})

        wrong = [p for p in expected_policy_set.intersection(actual_policy_set)
                 if expected_policy[p] != actual_policy[p]]
        for k in wrong:
            diff += ('Incorrect policy\n  %s != %s\n' %
                     ({k: expected_policy[k]}, {k: actual_policy[k]}))

        return diff or None


    def _get_expected_policies(self):
        """Read policy data from the policy expected file.

        Returns:
            A dictionary of policies.
        """
        policy_file = os.path.join(self.pyauto.DataDir(),
                                   self._POLICY_EXPECTED_FILE)
        if not os.path.exists(policy_file):
            raise error.TestError(
                'Expected policy data file does not exist (%s).' % policy_file)
        return self.pyauto.EvalDataFrom(policy_file)


    def _test_user_policies(self, user):
        """Login, fetch and verify mandatory user policies."""
        # Login and verify.
        credentials = self.pyauto.GetPrivateInfo()[user]
        self.login(credentials['username'], credentials['password'])

        # Get expected policy data.
        expected_policy = self._get_expected_policies()[user]

        # Get actual policy data and verify.
        self.pyauto.RefreshPolicies()
        actual_policy = self.pyauto.GetEnterprisePolicyInfo()
        diff = self._compare_policies(
            expected_policy['user_mandatory_policies'],
            actual_policy['user_mandatory_policies'])
        if diff:
            raise error.TestFail('Incorrect mandatory user policies:\n%s' %
                                 diff)


    def test_prod_enterprise_executive_user(self):
        self._test_user_policies('prod_enterprise_executive_user')


    def test_prod_enterprise_sales_user(self):
        self._test_user_policies('prod_enterprise_sales_user')


    def test_prod_enterprise_development_user(self):
        self._test_user_policies('prod_enterprise_development_user')


    def test_prod_enterprise_test_user(self):
        self._test_user_policies('prod_enterprise_test_user')


    def test_prod_enterprise_operations_user(self):
        self._test_user_policies('prod_enterprise_operations_user')


    def test_qa_enterprise_executive_user(self):
        self._test_user_policies('test_enterprise_executive_user')


    def test_qa_enterprise_sales_user(self):
        self._test_user_policies('test_enterprise_sales_user')


    def test_qa_enterprise_development_user(self):
        self._test_user_policies('test_enterprise_development_user')


    def test_qa_enterprise_test_user(self):
        self._test_user_policies('test_enterprise_test_user')


    def test_qa_enterprise_operations_user(self):
        self._test_user_policies('test_enterprise_operations_user')


    def test_enroll_unmanaged_domain(self):
        """Test that enrollment fails with an unmanaged account."""
        import pyauto_errors

        credentials = self.pyauto.GetPrivateInfo()[
            'prod_enterprise_disabled_domain']

        try:
            self.pyauto.EnrollEnterpriseDevice(credentials['username'],
                                               credentials['password'])
        except pyauto_errors.JSONInterfaceError:
            pass

        if self.pyauto.IsEnterpriseDevice():
            raise error.TestFail('Device was enrolled with an unmanaged domain')


    def test_enroll_bad_credential(self):
        """Test that enrollment fails with an invalid credential."""
        import pyauto_errors

        credentials = self.pyauto.GetPrivateInfo()[
            'prod_enterprise_executive_user']

        try:
            self.pyauto.EnrollEnterpriseDevice(credentials['username'],
                                               'BogusPassword')
        except pyauto_errors.JSONInterfaceError:
            pass

        if self.pyauto.IsEnterpriseDevice():
            raise error.TestFail('Device was enrolled with an invalid'
                                 'credential.')


    def _test_device_policies(self, user):
        """Enroll the device, login, fetch and verify mandatory device policies.
        """
        # Enroll the device and verify.
        credentials = self.pyauto.GetPrivateInfo()[user]
        try:
            self.pyauto.EnrollEnterpriseDevice(credentials['username'],
                                               credentials['password'])
        except:
            self.take_screenshot(fname_prefix='enrollment-fail-screenshot')
            raise

        if not self.pyauto.IsEnterpriseDevice():
            raise error.TestFail('Failed to enroll the device.')

        # Login and verify.
        self.login(credentials['username'], credentials['password'])

        # Get expected policy data.
        expected_policy = self._get_expected_policies()[user]

        # Get actual policy data and verify.
        self.pyauto.RefreshPolicies()
        actual_policy = self.pyauto.GetEnterprisePolicyInfo()
        diff = self._compare_policies(
            expected_policy['device_mandatory_policies'],
            actual_policy['device_mandatory_policies'])
        if diff:
            raise error.TestFail('Incorrect mandatory device policies:\n%s' %
                                 diff)


    def test_crosqa2_device_policies(self):
        self._test_device_policies('test_enterprise_crosqa2_user')


    def test_crosqa3_device_policies(self):
        self._test_device_policies('test_enterprise_crosqa3_user')


    def test_crosqa4_device_policies(self):
        self._test_device_policies('test_enterprise_crosqa4_user')


    def test_crosprqa2_device_policies(self):
        self._test_device_policies('prod_enterprise_crosprqa2_user')


    def test_crosprqa3_device_policies(self):
        self._test_device_policies('prod_enterprise_crosprqa3_user')


    def test_crosprqa4_device_policies(self):
        self._test_device_policies('prod_enterprise_crosprqa4_user')
