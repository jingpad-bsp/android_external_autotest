# Copyright 2015 The Chromium OS Authors. All rights reserved.
# Use of this source code is governed by a BSD-style license that can be
# found in the LICENSE file.

import logging
import utils

from autotest_lib.client.common_lib import error
from autotest_lib.client.cros import enterprise_policy_base
from autotest_lib.client.cros import httpd


class policy_ImagesBlockedForUrls(enterprise_policy_base.EnterprisePolicyTest):
    """Test ImagesBlockedForUrls policy effect on CrOS look & feel.

    This test verifies the behavior of Chrome OS with a range of valid values
    for the ImagesBlockedForUrls user policy, as encapsulated by four test
    cases, named: NotSet, 1Url, 2Urls, and 3Urls.

    When policy value is None (as in case=NotSet), then images are not blocked
    on any page. When the value is set to a single URL (case=1Url), then
    images are blocked on any page with the same domain as the URL. When set
    to multiple URLs (as in case=2Urls or 3Urls), then images are blocked on
    any page that has the same domain as any of the specified URLs.

    Two of the test cases (1Url, 3Urls) expect images to be blocked, and the
    other two (NotSet, 2Urls) expect images to be allowed.

    Note this test has a dependency on the DefaultImagesSetting policy, which
    is partially tested herein and by the test for ImagesAllowedForUrls. For
    this test, we set DefaultImagesSetting=1 (or null), which allows images on
    all pages except those listed in ImagesBlockedForUrls. For the test of
    ImagesAllowedForUrls, we set DefaultImagesSetting=2, which blocks images
    on all pages except those listed in ImagesAllowedForUrls.

    """
    version = 1

    POLICY_NAME = 'ImagesBlockedForUrls'
    URL_HOST = 'http://localhost'
    URL_PORT = 8080
    URL_BASE = '%s:%d' % (URL_HOST, URL_PORT)
    URL_PAGE = '/kittens.html'
    TEST_URL = URL_BASE + URL_PAGE

    URL1_DATA = [URL_HOST]
    URL2_DATA = ['http://www.bing.com', 'https://www.yahoo.com']
    URL3_DATA = ['http://www.bing.com', URL_BASE,
                 'https://www.yahoo.com']

    TEST_CASES = {
        'NotSet': '',
        '1Url': URL1_DATA,
        '2Urls': URL2_DATA,
        '3Urls': URL3_DATA
    }

    STARTUP_URLS = ['chrome://policy', 'chrome://settings']
    SUPPORTING_POLICIES = {
        'DefaultImagesSetting': 1,
        'BookmarkBarEnabled': False,
        'RestoreOnStartupURLs': STARTUP_URLS,
        'RestoreOnStartup': 4
    }

    def _wait_for_page_ready(self, tab):
        utils.poll_for_condition(
            lambda: tab.EvaluateJavaScript('pageReady'),
            exception=error.TestError('Test page is not ready.'))

    def _test_images_blocked_for_urls(self, policy_value, policies_json):
        """
        Verify CrOS enforces the ImagesBlockedForUrls policy.

        When ImagesBlockedForUrls is undefined, images shall not be blocked on
        any page. When ImagesBlockedForUrls contains one or more URLs, images
        are blocked on any page whose domain matches any of the listed URLs.

        @param policy_value: policy value expected on chrome://policy page.
        @param policies_json: policy JSON data to send to the fake DM server.

        """
        self.setup_case(self.POLICY_NAME, policy_value, policies_json)
        logging.info('Running _test_images_blocked_for_urls(%s, %s)',
                     policy_value, policies_json)

        try:
            web_server = httpd.HTTPListener(
                self.URL_PORT, docroot=self.bindir)
            web_server.run()
        except Exception as err:
            logging.info('Timeout starting HTTP listener.')
            raise error.TestFailRetry(err)

        tab = self.cr.browser.tabs.New()
        tab.Activate()
        tab.Navigate(self.TEST_URL, timeout=4)
        tab.WaitForDocumentReadyStateToBeComplete()
        self._wait_for_page_ready(tab)
        image_is_blocked = tab.EvaluateJavaScript(
            "document.getElementById('kittens_id').width") == 0

        if policy_value is not None and self.URL_HOST in policy_value:
            if not image_is_blocked:
                raise error.TestFail('Image should be blocked.')
        else:
            if image_is_blocked:
                raise error.TestFail('Image should not be blocked.')

        tab.Close()
        if web_server:
            web_server.stop()

    def _run_test_case(self, case):
        """
        Setup and run the test configured for the specified test case.

        Set the expected |policy_value| and |policies_json| data based on the
        test |case|. If the user specified an expected |value|, then use it to
        set the |policy_value| and blank out |policies_json|.

        @param case: Name of the test case to run.

        """
        if case not in self.TEST_CASES:
            raise error.TestError('Test case %s is not valid.' % case)

        # If |value| was given in the command line args, then set expected
        # |policy_value| to the given value, and |policies_json| to None.
        if self.is_value_given:
            policy_value = self.value
            policies_json = None

        # Otherwise, set expected |policy_value| and setup |policies_json|
        # data to the values required by the test |case|.
        else:
            policies_json = self.SUPPORTING_POLICIES.copy()
            if case == 'NotSet':
                policy_value = None
                policy_json = {'ImagesBlockedForUrls': None}
            elif case == '1Url':
                policy_value = ','.join(self.URL1_DATA)
                policy_json = {'ImagesBlockedForUrls': self.URL1_DATA}
            elif case == '2Urls':
                policy_value = ','.join(self.URL2_DATA)
                policy_json = {'ImagesBlockedForUrls': self.URL2_DATA}
            elif case == '3Urls':
                policy_value = ','.join(self.URL3_DATA)
                policy_json = {'ImagesBlockedForUrls': self.URL3_DATA}
            policies_json.update(policy_json)

        # Run test using the values configured for the test case.
        self._test_images_blocked_for_urls(policy_value, policies_json)

    def run_once(self):
        """Main runner for the test cases."""
        if self.mode == 'all':
            for case in sorted(self.TEST_CASES):
                self._run_test_case(case)
        elif self.mode == 'single':
            self._run_test_case(self.case)
        elif self.mode == 'list':
            logging.info('List Test Cases:')
            for case, value in sorted(self.TEST_CASES.items()):
                logging.info('  case=%s, value="%s"', case, value)
        else:
            raise error.TestError('Run mode %s is not valid.' % self.mode)
