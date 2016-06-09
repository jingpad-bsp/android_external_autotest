# Copyright 2015 The Chromium OS Authors. All rights reserved.
# Use of this source code is governed by a BSD-style license that can be
# found in the LICENSE file.

import logging
import time
import utils

from autotest_lib.client.common_lib import error
from autotest_lib.client.cros import enterprise_policy_base


class policy_JavaScriptBlockedForUrls(
    enterprise_policy_base.EnterprisePolicyTest):
    """Test JavaScriptBlockedForUrls policy effect on CrOS look & feel.

    This test verifies the behavior of Chrome OS with a range of valid values
    for the JavaScriptBlockedForUrls user policy, covered by four named test
    cases: NotSet_Allow, SingleUrl_Block, MultipleUrls_Allow, and
    MultipleUrls_Block.

    When the policy value is None (as in test case=NotSet_Allow), then
    JavaScript execution be allowed on any page. When the policy value is set
    to a single URL pattern (as in test case=SingleUrl_Block), then
    JavaScript execution will be blocked on any page that matches that
    pattern. When set to multiple URL patterns (as case=MultipleUrls_Allow
    and MultipleUrls_Block) then JavaScript execution will be blocked on any
    page with an URL that matches any of the listed patterns.

    Two test cases (NotSet_Allow, MultipleUrls_Allow) are designed to allow
    JavaScript execution the test page. The other two test cases
    (NotSet_Allow, MultipleUrls_Block) are designed to block JavaScript
    execution on the test page.

    Note this test has a dependency on the DefaultJavaScriptSetting user
    policy, which is tested partially herein and in the test
    policy_JavaScriptAllowedForUrls. For this test, we set
    DefaultJavaScriptSetting=1. This allows JavaScript execution on all pages
    except those with a URL matching a pattern in JavaScriptBlockedForUrls.
    In the test policy_JavaScriptAllowedForUrls, we set
    DefaultJavaScriptSetting=2. That test blocks JavaScript execution on all
    pages except those with an URL matching a pattern in
    JavaScriptAllowedForUrls.

    """
    version = 1

    POLICY_NAME = 'JavaScriptBlockedForUrls'
    URL_HOST = 'http://localhost'
    URL_PORT = 8080
    URL_BASE = '%s:%d' % (URL_HOST, URL_PORT)
    URL_PAGE = '/js_test.html'
    TEST_URL = URL_BASE + URL_PAGE

    TEST_CASES = {
        'NotSet_Allow': None,
        'SingleUrl_Block': [URL_BASE],
        'MultipleUrls_Allow': ['http://www.bing.com',
                               'https://www.yahoo.com'],
        'MultipleUrls_Block': ['http://www.bing.com',
                               TEST_URL,
                               'https://www.yahoo.com']
    }

    STARTUP_URLS = ['chrome://policy', 'chrome://settings']
    SUPPORTING_POLICIES = {
        'DefaultJavaScriptSetting': 1,
        'BookmarkBarEnabled': False,
        'RestoreOnStartupURLs': STARTUP_URLS,
        'RestoreOnStartup': 4
    }

    def initialize(self, args=()):
        super(policy_JavaScriptBlockedForUrls, self).initialize(args)
        self.start_webserver(self.URL_PORT)

    def _can_execute_javascript(self, tab):
        """Determine whether JavaScript is allowed to run on the given page.

        @param tab: browser tab containing JavaScript to run.

        """
        try:
            utils.poll_for_condition(
                lambda: tab.EvaluateJavaScript('jsAllowed', timeout=2),
                exception=error.TestError('Test page is not ready.'))
            return True
        except:
            return False

    def _test_javascript_blocked_for_urls(self, policy_value, policies_dict):
        """Verify CrOS enforces the JavaScriptBlockedForUrls policy.

        When JavaScriptBlockedForUrls is undefined, JavaScript execution shall
        be allowed on all pages. When JavaScriptBlockedForUrls contains one or
        more URL patterns, JavaScript execution shall be allowed only on the
        pages whose URL matches any of the listed patterns.

        @param policy_value: policy value expected on chrome://policy page.
        @param policies_dict: policy dict data to send to the fake DM server.

        """
        logging.info('Running _test_javascript_blocked_for_urls(%s, %s)',
                     policy_value, policies_dict)
        self.setup_case(self.POLICY_NAME, policy_value, policies_dict)

        tab = self.cr.browser.tabs.New()
        tab.Activate()
        tab.Navigate(self.TEST_URL)
        time.sleep(1)

        utils.poll_for_condition(
            lambda: tab.url == self.TEST_URL,
            exception=error.TestError('Test page is not ready.'))
        javascript_is_allowed = self._can_execute_javascript(tab)

        if policy_value is not None and self.URL_HOST in policy_value:
            # If |URL_HOST| is in |policy_value|, then JavaScript execution
            # should be blocked. If execution is allowed, raise an error.
            if javascript_is_allowed:
                raise error.TestFail('JavaScript should be blocked.')
        else:
            if not javascript_is_allowed:
                raise error.TestFail('JavaScript should be allowed.')
        tab.Close()

    def run_test_case(self, case):
        """Setup and run the test configured for the specified test case.

        Set the expected |policy_value| string and |policies_dict| data based
        on the test |case|. If the user specified an expected |value| in the
        command line args, then use it to set the |policy_value| and blank out
        the |policies_dict|.

        @param case: Name of the test case to run.

        """
        policy_value, policies_dict = self._get_policy_data_for_case(case)

        # Run test using the values configured for the test |case|.
        self._test_javascript_blocked_for_urls(policy_value, policies_dict)
