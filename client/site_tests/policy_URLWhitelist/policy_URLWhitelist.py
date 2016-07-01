# Copyright 2015 The Chromium OS Authors. All rights reserved.
# Use of this source code is governed by a BSD-style license that can be
# found in the LICENSE file.

import logging

from autotest_lib.client.common_lib import error
from autotest_lib.client.cros import enterprise_policy_base


class policy_URLWhitelist(enterprise_policy_base.EnterprisePolicyTest):
    """Test effect of URLWhitleist policy on Chrome OS behavior.

    Navigate to all the websites in the BLOCKED_URLS_LIST. Verify that the
    websites specified by the URLWhitelist policy value are allowed. Also
    verify that the websites not in the URLWhitelist policy value are blocked.

    Two TEST_CASES (SinglePage_Allowed, MultiplePages_Allowed) are designed to
    verify that a website is allowed regardless of whether a single webpage is
    specified in the URLWhitelist policy, or multiple webpages are specified.
    The third TEST_CASE (NotSet_Blocked) is designed to verify that all
    websites are blocked since the URLWhitelistlist policy is set to None.

    The test case shall pass if the URLs that are part of the URLWhitelist
    policy value are allowed. The test case shall also pass if the URLs that
    are not part of the URLWhitelist policy value are blocked. The test case
    shall fail if the above behavior is not enforced.

    """
    version = 1

    POLICY_NAME = 'URLWhitelist'
    URL_HOST = 'http://localhost'
    URL_PORT = 8080
    URL_BASE = '%s:%d/%s' % (URL_HOST, URL_PORT, 'test_data')
    BLOCKED_URLS_LIST = [URL_BASE + website for website in
                          ['/website1.html',
                           '/website2.html',
                           '/website3.html']]
    SINGLE_WHITELISTED_FILE_DATA = BLOCKED_URLS_LIST[:1]
    MULTIPLE_WHITELISTED_FILES_DATA = BLOCKED_URLS_LIST[:2]
    BLOCKED_USER_MESSAGE = 'Webpage Blocked'
    BLOCKED_ERROR_MESSAGE = 'ERR_BLOCKED_BY_ADMINISTRATOR'

    TEST_CASES = {
        'NotSet_Blocked': None,
        'SinglePage_Allowed': SINGLE_WHITELISTED_FILE_DATA,
        'MultiplePages_Allowed': MULTIPLE_WHITELISTED_FILES_DATA
    }
    SUPPORTING_POLICIES = {'URLBlacklist': BLOCKED_URLS_LIST}

    def initialize(self, args=()):
        super(policy_URLWhitelist, self).initialize(args)
        self.start_webserver(self.URL_PORT)

    def _scrape_text_from_webpage(self, tab):
        """Return a list of filtered text on the web page.

        @param tab: tab containing the website to be parsed.
        @raises: TestFail if the expected text was not found on the page.

        """
        parsed_message_string = ''
        parsed_message_list = []
        page_scrape_cmd = 'document.getElementById("main-message").innerText;'
        try:
            parsed_message_string = tab.EvaluateJavaScript(page_scrape_cmd)
        except Exception as err:
                raise error.TestFail('Unable to find the expected '
                                     'text content on the test '
                                     'page: %s\n %r'%(tab.url, err))
        logging.info('Parsed message:%s', parsed_message_string)
        parsed_message_list = [str(word) for word in
                               parsed_message_string.split('\n') if word]
        return parsed_message_list

    def _is_url_blocked(self, url):
        """Return True if the URL is blocked else returns False.

        @param url: The URL to be checked whether it is blocked.

        """
        parsed_message_list = []
        tab = self.navigate_to_url(url)
        parsed_message_list = self._scrape_text_from_webpage(tab)
        if len(parsed_message_list) == 2 and \
                parsed_message_list[0] == 'Website enabled' and \
                parsed_message_list[1] == 'Website is enabled':
            return False

        # Check if accurate user error message is shown on the error page.
        if parsed_message_list[0] != self.BLOCKED_USER_MESSAGE or \
                parsed_message_list[1] != self.BLOCKED_ERROR_MESSAGE:
            logging.warning('The Blocked page user notification '
                            'messages, %s and %s are not displayed on '
                            'the blocked page. The messages may have '
                            'been modified. Please check and update the '
                            'messages in this file accordingly.',
                            self.BLOCKED_USER_MESSAGE,
                            self.BLOCKED_ERROR_MESSAGE)
        return True

    def _test_url_whitelist(self, policy_value, policies_dict):
        """Verify CrOS enforces URLWhitelist policy value.

        Navigate to all the websites in the BLOCKED_URLS_LIST. Verify that
        the websites specified by the URLWhitelist policy value allowed.
        Also verify that the websites not in the URLWhitelist policy value
        are blocked.

        @param policy_value: policy value expected on chrome://policy page.
        @param policies_dict: policy dict data to send to the fake DM server.
        @raises: TestFail if url is blocked/not blocked based on the
                 corresponding policy values.

        """
        logging.info('Running _test_url_whitelist(%s, %s)',
                     policy_value, policies_dict)
        self.setup_case(self.POLICY_NAME, policy_value, policies_dict)

        for url in self.BLOCKED_URLS_LIST:
            url_is_blocked = self._is_url_blocked(url)
            if policy_value:
                if url in policy_value and url_is_blocked:
                    raise error.TestFail('The URL %s should have been '
                                         'allowed by policy, but it '
                                         'was blocked.' % url)
                elif url not in policy_value and not url_is_blocked:
                    raise error.TestFail('The URL %s should have been '
                                         'blocked by policy, but it '
                                         'was allowed.' % url)

            elif not url_is_blocked:
                raise error.TestFail('The URL %s should have been blocked'
                                      'by policy, but it was allowed.' % url)

    def run_test_case(self, case):
        """Setup and run the test configured for the specified test case.

        Set the expected |policy_value| and |policies_dict| data defined for
        the specified test |case|, and run the test. If the user specified an
        expected |value| in the command line args, then it will be used to set
        the |policy_value|.

        @param case: Name of the test case to run.

        """
        policy_value, policies_dict = self._get_policy_data_for_case(case)
        self._test_url_whitelist(policy_value, policies_dict)
