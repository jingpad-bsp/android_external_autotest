# Copyright 2015 The Chromium OS Authors. All rights reserved.
# Use of this source code is governed by a BSD-style license that can be
# found in the LICENSE file.

import logging

from autotest_lib.client.common_lib import error
from autotest_lib.client.cros import enterprise_policy_base


class policy_RestoreOnStartupURLs(enterprise_policy_base.EnterprisePolicyTest):
    """
    Test effect of RestoreOnStartupURLs policy on Chrome OS behavior.

    This test verifies the behavior of Chrome OS for a range of valid values
    in the RestoreOnStartupURLs user policy. The values are covered by three
    test cases:
    = 1URL: Opens a single tab to the chrome://settings page.
    = 3URLs: Opens 3 tabs in order to the following pages:
    'chrome://policy,chrome://settings,chrome://histograms'
    = NotSet: Opens no tabs. This is the default behavior for un-managed
    user and guest user sessions.

    """
    version = 1

    POLICY_NAME = 'RestoreOnStartupURLs'
    TEST_CASES = ['1URL', '3URLs', 'NotSet']
    URLS1_DATA = ['chrome://settings']
    URLS3_DATA = ['chrome://policy', 'chrome://settings',
                  'chrome://histograms']

    def _test_StartupURLs(self, policy_value, policies_json):
        """
        Verify CrOS enforces RestoreOnStartupURLs policy value.

        When RestoreOnStartupURLs policy is set to one or more URLs, check
        that a tab is opened to each URL. When set to None, check that no tab
        is opened.

        @param policy_value: policy value expected on chrome://policy page.
        @param policies_json: policy JSON data to send to the fake DM server.

        """
        self.setup_case(self.POLICY_NAME, policy_value, policies_json)
        logging.info('Running _test_StartupURLs(%s, %s)',
                     policy_value, policies_json)

        # Get list of open tab urls from browser; Convert unicode to text;
        # Strip trailing '/' character reported by devtools.
        tab_urls = [tab.url.encode('utf8').rstrip('/')
                    for tab in reversed(self.cr.browser.tabs)]
        tab_urls_value = ','.join(tab_urls)

        # Telemetry always opens a 'newtab' tab if no tabs are opened. If the
        # only open tab is a 'newtab' tab, then set tab URLs to None.
        if tab_urls_value == 'chrome://newtab':
            tab_urls_value = None

        # Compare open tabs with expected tabs by |policy_value|.
        if tab_urls_value != policy_value:
            raise error.TestFail('Unexpected tabs: %s '
                                 '(expected: %s)' %
                                 (tab_urls_value, policy_value))

    def _run_test_case(self, case):
        """
        Run the test case given by |case|.

        @param case: Name of the test case to run.

        """
        if case not in self.TEST_CASES:
            raise error.TestError('Test case %s is not valid.' % case)

        # If using the local fake DM Server, set policy JSON and expected
        # value to the defaults required by the test |case|.
        if self.env == 'dm-fake':
            if case == '1URL':
                policy_json = self.URLS1_DATA
                policy_value = ','.join(self.URLS1_DATA)
            elif case == '3URLs':
                policy_json = self.URLS3_DATA
                policy_value = ','.join(self.URLS3_DATA)
            elif case == 'NotSet':
                policy_json = None
                policy_value = None

            # Add supporting policy data to policies JSON.
            if policy_json is None:
                policies_json = {'RestoreOnStartupURLs': policy_json,
                                 'RestoreOnStartup': None
                                }
            else:
                policies_json = {'RestoreOnStartupURLs': policy_json,
                                 'RestoreOnStartup': 4
                                }
        # If using an external DM Server, set policy expected value to the
        # given value (if any), or to the default required by the test |case|.
        else:
            policies_json = None
            if self.is_value_given:
                policy_value = self.value
            elif case == '1URL':
                policy_value = ','.join(self.URLS1_DATA)
            elif case == '3URLs':
                policy_value = ','.join(self.URLS3_DATA)
            elif case == 'NotSet':
                policy_value = None

        self._test_StartupURLs(policy_value, policies_json)

    def run_once(self):
        """Main runner for the test cases."""
        if self.mode == 'all':
            for case in self.TEST_CASES:
                self._run_test_case(case)
        elif self.mode == 'single':
            self._run_test_case(self.case)
        elif self.mode == 'list':
            logging.info('List Test Cases:')
            for case in self.TEST_CASES:
                logging.info('  %s', case)
        else:
            raise error.TestError('Run mode %s is not valid.' % self.mode)

