# Copyright 2015 The Chromium OS Authors. All rights reserved.
# Use of this source code is governed by a BSD-style license that can be
# found in the LICENSE file.

# Copyright 2015 The Chromium OS Authors. All rights reserved.
# Use of this source code is governed by a BSD-style license that can be
# found in the LICENSE file.

import logging

from autotest_lib.client.common_lib import error
from autotest_lib.client.cros import enterprise_policy_base


class policy_CookiesBlockedForUrls(enterprise_policy_base.EnterprisePolicyTest):
    """Test effect of the CookiesBlockedForUrls policy on Chrome OS behavior.

    This test implicitly verifies one value of the DefaultCookiesSetting
    policy as well. When DefaultCookiesSetting is set to 1, cookies for all
    URLs shall be stored (i.e., shall be not blocked), except for the URL
    patterns specified by the CookiesBlockedForUrls policy value.

    The test verifies ChromeOS behaviour for different values of the
    CookiesBlockedForUrls policy, i.e., for the policy value set to Not Set,
    set to a single url/host pattern, or when the policy is set to multiple
    url/host patterns. It also verifies that cookies are allowed for urls that
    are not part of the policy value.

    The corresponding three test cases are NotSet_CookiesAllowed,
    SingleUrl_CookiesBlocked, MultipleUrls_CookiesBlocked and
    MultipleUrls_CookiesAllowed.

    """
    version = 1

    POLICY_NAME = 'CookiesBlockedForUrls'
    URL_BASE = 'http://localhost'
    URL_PORT = 8080
    URL_HOST = '%s:%d'%(URL_BASE, URL_PORT)
    URL_RESOURCE = '/test_data/testWebsite1.html'
    TEST_URL = URL_HOST + URL_RESOURCE
    COOKIE_NAME = 'cookie1'
    COOKIE_BLOCKED_SINGLE_FILE_DATA = [URL_HOST]
    COOKIE_BLOCKED_MULTIPLE_FILES_DATA = ['http://google.com', URL_HOST,
                                          'http://doesnotmatter.com']
    COOKIE_ALLOWED_MULTIPLE_FILES_DATA = ['https://testingwebsite.html'
                                          'https://somewebsite.com',
                                          'http://doesnotmatter.com']

    TEST_CASES = {
        'NotSet_CookiesAllowed': '',
        'SingleUrl_CookiesBlocked': COOKIE_BLOCKED_SINGLE_FILE_DATA,
        'MultipleUrls_CookiesBlocked': COOKIE_BLOCKED_MULTIPLE_FILES_DATA,
        'MultipleUrls_CookiesAllowed' : COOKIE_ALLOWED_MULTIPLE_FILES_DATA
    }

    SUPPORTING_POLICIES = {'DefaultCookiesSetting': 1}

    def initialize(self, args=()):
        super(policy_CookiesBlockedForUrls, self).initialize(args)
        self.start_webserver(self.URL_PORT)

    def _is_cookie_blocked(self, url):
        """Return True if the cookie is blocked for the URL else returns False.

        @param url: Url of the page which is loaded to check whether it's
                    cookie is blocked or stored.

        """
        tab =  self.navigate_to_url(url)
        return tab.GetCookieByName(self.COOKIE_NAME) is None

    def _test_cookies_blocked_for_urls(self, policy_value, policies_dict):
        """Verify CrOS enforces CookiesBlockedForUrls policy value.

        When the CookiesBlockedForUrls policy is set to one or more urls/hosts,
        check that cookies are blocked for the urls/urlpatterns listed in
        the policy value. When set to None, check that cookies are allowed for
        all URLs.

        @param policy_value: policy value expected on chrome://policy page.
        @param policies_dict: policy dict data to send to the fake DM server.
        @raises: TestFail if cookies are blocked/not blocked based on the
                 corresponding policy values.

        """
        logging.info('Running _test_cookies_blocked_for_urls(%s, %s)',
                     policy_value, policies_dict)
        self.setup_case(self.POLICY_NAME, policy_value, policies_dict)

        cookie_is_blocked = self._is_cookie_blocked(self.TEST_URL)

        if policy_value and self.URL_HOST in policy_value:
            if not cookie_is_blocked:
                raise error.TestFail('Cookies should be blocked.')
        else:
            if cookie_is_blocked:
                raise error.TestFail('Cookies should be allowed.')

    def run_test_case(self, case):
        """Setup and run the test configured for the specified test case.

        Set the expected |policy_value| and |policies_dict| data defined for
        the specified test |case|, and run the test. If the user specified an
        expected |value| in the command line args, then it will be used to set
        the |policy_value|.

        @param case: Name of the test case to run.

        """
        policy_value, policies_dict = self._get_policy_data_for_case(case)

        # Run test using the values configured for the test case.
        self._test_cookies_blocked_for_urls(policy_value, policies_dict)
