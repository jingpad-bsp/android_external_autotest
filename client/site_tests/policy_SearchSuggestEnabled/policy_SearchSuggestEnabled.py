# Copyright 2016 The Chromium OS Authors. All rights reserved.
# Use of this source code is governed by a BSD-style license that can be
# found in the LICENSE file.

# pylint: disable=module-missing-docstring
# pylint: disable=docstring-section-name
# pylint: disable=no-init
# pylint: disable=g-wrong-blank-lines

import logging

from autotest_lib.client.common_lib import error
from autotest_lib.client.cros import enterprise_policy_base


class policy_SearchSuggestEnabled(enterprise_policy_base.EnterprisePolicyTest):
    """Test effect of SearchSuggestEnabled policy on Chrome OS behavior.

    This test verifies the behavior of Chrome OS for all valid values of the
    SearchSuggestEnabled user policy: True, False, and Not set. 'Not set'
    indicates no value, and will induce the default behavior that is seen by
    an unmanaged user: checked and user-editable.

    When True or Not set, search suggestions are given. When False, search
    suggestions are not given. When set either True or False, the setting is
    disabled, so users cannot change or override the setting. When not set
    users can change the setting.
    """
    version = 1

    POLICY_NAME = 'SearchSuggestEnabled'
    STARTUP_URLS = ['chrome://policy']
    SUPPORTING_POLICIES = {
        'BookmarkBarEnabled': True,
        'RestoreOnStartupURLs': STARTUP_URLS,
        'RestoreOnStartup': 4
    }
    TEST_CASES = {
        'True_Enable': True,
        'False_Disable': False,
        'NotSet_Enable': None
    }
    CHROME_SETTINGS_PAGE = 'chrome://settings'
    LABEL_TEXT = 0
    INPUT_CHECKED = 1
    INPUT_DISABLED = 2


    def _get_checkbox_properties(self, pref):
        """Get Search Suggest setting properties from the settings page.

        @param pref: pref attribute value for the setting check box.
        @returns: element properties of the setting check box.
        """
        js_get_checkbox_props = ('''
        settings = document.getElementsByClassName(
                'checkbox controlled-setting-with-label');
        settingValues = '';
        for (var i = 0, setting; setting = settings[i]; i++) {
           var setting_label = setting.getElementsByTagName("label")[0];
           var label_input = setting_label.getElementsByTagName("input")[0];
           var input_pref = label_input.getAttribute("pref");
           if (input_pref == '%s') {
              settingValues = [setting_label.innerText.trim(),
                               label_input.checked, label_input.disabled];
              break;
           }
        }
        settingValues;
        ''' % pref)

        settings_tab = self.navigate_to_url(self.CHROME_SETTINGS_PAGE)
        checkbox_props = settings_tab.EvaluateJavaScript(js_get_checkbox_props)
        settings_tab.Close()
        return checkbox_props


    def _test_search_suggest_enabled(self, policy_value, policies_dict):
        """Verify CrOS enforces SearchSuggestEnabled policy.

        @param policy_value: policy value expected on chrome://policy page.
        @param policies_dict: policy dict data to send to the fake DM server.
        """
        logging.info('Running _test_search_suggest_enabled(%s, %s)',
                     policy_value, policies_dict)
        self.setup_case(self.POLICY_NAME, policy_value, policies_dict)

        setting_pref = 'search.suggest_enabled'
        setting_properties = self._get_checkbox_properties(setting_pref)
        setting_label = setting_properties[self.LABEL_TEXT]
        setting_is_checked = setting_properties[self.INPUT_CHECKED]
        setting_is_disabled = setting_properties[self.INPUT_DISABLED]
        logging.info("Check box '%s' status: checked=%s, disabled=%s",
                     setting_label, setting_is_checked, setting_is_disabled)

        # Setting checked if policy is True, unchecked if False.
        if policy_value == 'true' and not setting_is_checked:
            raise error.TestFail('Search Suggest should be checked.')
        if policy_value == 'false' and setting_is_checked:
            raise error.TestFail('Search Suggest should be unchecked.')

        # Setting is enabled if policy is Not set, disabled if True or False.
        if policy_value == 'null':
            if setting_is_disabled:
                raise error.TestFail('Search Suggest should be editable.')
        else:
            if not setting_is_disabled:
                raise error.TestFail('Search Suggest should not be editable.')


    def run_test_case(self, case):
        """Setup and run the test configured for the specified test case.

        Set the expected |policy_value| and |policies_dict| data defined for
        the specified test |case|, and run the test.

        @param case: Name of the test case to run.
        """
        policy_value = self.packed_json_string(self.TEST_CASES[case])
        policy_dict = {self.POLICY_NAME: self.TEST_CASES[case]}
        policies_dict = self.SUPPORTING_POLICIES.copy()
        policies_dict.update(policy_dict)
        self._test_search_suggest_enabled(policy_value, policies_dict)
