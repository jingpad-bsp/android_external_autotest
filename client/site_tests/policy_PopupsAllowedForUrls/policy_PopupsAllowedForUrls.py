# Copyright 2015 The Chromium OS Authors. All rights reserved.
# Use of this source code is governed by a BSD-style license that can be
# found in the LICENSE file.

import logging, utils

from autotest_lib.client.common_lib import error
from autotest_lib.client.cros import enterprise_policy_base


class policy_PopupsAllowedForUrls(enterprise_policy_base.EnterprisePolicyTest):
    """Test PopupsAllowedForUrls policy effect on CrOS look & feel.

    This test verifies the behavior of Chrome OS with a range of valid values
    for the PopupsAllowedForUrls user policy, when DefaultPopupsSetting=2
    (i.e., block popups by default on all pages except those in domains listed
    in PopupsAllowedForUrls). These valid values are covered by 4 test cases,
    named: NotSet_Blocked, 1Url_Allowed, 2Urls_Blocked, and 3Urls_Allowed.

    When the policy value is None (as in case NotSet_Blocked), then popups are
    blocked on any page. When the value is set to one or more URLs (as in
    1Url_Allowed, 2Urls_Blocked, and 3Urls_Allowed), popups are allowed only
    on pages with a domain that matches any of the listed URLs, and blocked on
    any of those that do not match.

    As noted above, this test requires the DefaultPopupsSetting policy to be
    set to 2. A related test, policy_PopupsBlockedForUrls, requires the value
    to be set to 1. That value allows popups on all pages except those with
    domains listed in PopupsBlockedForUrls.

    """
    version = 1

    POLICY_NAME = 'PopupsAllowedForUrls'
    URL_HOST = 'http://localhost'
    URL_PORT = 8080
    URL_BASE = '%s:%d' % (URL_HOST, URL_PORT)
    URL_PAGE = '/popup_status.html'
    TEST_URL = URL_BASE + URL_PAGE

    URL1_DATA = [URL_HOST]
    URL2_DATA = ['http://www.bing.com', 'https://www.yahoo.com']
    URL3_DATA = ['http://www.bing.com', URL_BASE,
                 'https://www.yahoo.com']
    TEST_CASES = {
        'NotSet_Block': None,
        '1Url_Allow': URL1_DATA,
        '2Urls_Block': URL2_DATA,
        '3Urls_Allow': URL3_DATA
    }
    STARTUP_URLS = ['chrome://policy', 'chrome://settings']
    SUPPORTING_POLICIES = {
        'DefaultPopupsSetting': 2,
        'BookmarkBarEnabled': False,
        'RestoreOnStartupURLs': STARTUP_URLS,
        'RestoreOnStartup': 4
    }

    def initialize(self, **kwargs):
        super(policy_PopupsAllowedForUrls, self).initialize(**kwargs)
        self.start_webserver(self.URL_PORT)

    def _wait_for_page_ready(self, tab):
        utils.poll_for_condition(
            lambda: tab.EvaluateJavaScript('pageReady'),
            exception=error.TestError('Test page is not ready.'))

    def _test_popups_allowed_for_urls(self, policy_value, policies_dict):
        """Verify CrOS enforces the PopupsAllowedForUrls policy.

        When PopupsAllowedForUrls is undefined, popups shall be blocked on
        all pages. When PopupsAllowedForUrls contains one or more URLs,
        popups shall be allowed only on the pages whose domain matches any of
        the listed URLs.

        @param policy_value: policy value expected on chrome://policy page.
        @param policies_dict: policy dict data to send to the fake DM server.

        """
        self.setup_case(self.POLICY_NAME, policy_value, policies_dict)
        logging.info('Running _test_popups_allowed_for_urls(%s, %s)',
                     policy_value, policies_dict)

        tab = self.navigate_to_url(self.TEST_URL)
        self._wait_for_page_ready(tab)
        is_blocked = tab.EvaluateJavaScript('isPopupBlocked();')

        # String |URL_HOST| will be found in string |policy_value| for
        # test cases 1Url_Allowed and 3Urls_Allowed, but not for cases
        # NotSet_Blocked and 2Urls_Blocked.
        if policy_value is not None and self.URL_HOST in policy_value:
            if is_blocked:
                raise error.TestFail('Popups should not be blocked.')
        else:
            if not is_blocked:
                raise error.TestFail('Popups should be blocked.')
        tab.Close()

    def run_test_case(self, case):
        """Setup and run the test configured for the specified test case.

        Set the expected |policy_value| and |policies_dict| data defined for
        the specified test |case|, and run the test.

        @param case: Name of the test case to run.

        """
        policy_value, policies_dict = self._get_policy_data_for_case(case)

        # Run test using the values configured for the test case.
        self._test_popups_allowed_for_urls(policy_value, policies_dict)
