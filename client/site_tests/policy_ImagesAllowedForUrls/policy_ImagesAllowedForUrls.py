# Copyright 2015 The Chromium OS Authors. All rights reserved.
# Use of this source code is governed by a BSD-style license that can be
# found in the LICENSE file.

import logging, utils

from autotest_lib.client.common_lib import error
from autotest_lib.client.cros import enterprise_policy_base


class policy_ImagesAllowedForUrls(enterprise_policy_base.EnterprisePolicyTest):
    """Test ImagesAllowedForUrls policy effect on CrOS look & feel.

    This test verifies the behavior of Chrome OS with a range of valid values
    for the ImagesAllowedForUrls user policies. These values are covered by
    four test cases, named: NotSet_Blocked, 1Url_Allowed, 2Urls_Blocked, and
    3Urls_Allowed.

    When the policy value is None (as in case=NotSet_Blocked), then images are
    blocked on any page. When the value is set to a single domain (such as
    case=1Url_Allowed), images are allowed on any page with that domain. When
    set to multiple domains (as in case=2Urls_Blocked or 3Urls_Allowed), then
    images are allowed on any page with a domain that matches any of the
    listed domains.

    Two test cases (1Url_Allowed, 3Urls_Allowed) are designed to allow images
    to be shown on the test page. The other two test cases (NotSet_Blocked,
    2Urls_Blocked) are designed to block images on the test page.

    Note this test has a dependency on the DefaultImagesSetting policy, which
    is partially tested herein, and by the test policy_ImagesBlockedForUrls.
    For this test, we set DefaultImagesSetting=2. This blocks images on all
    pages except those with a domain listed in ImagesAllowedForUrls. For the
    test policy_ImagesBlockedForUrls, we set DefaultImagesSetting=1. That
    allows images to be shown on all pages except those with domains listed in
    ImagesBlockedForUrls.

    """
    version = 1

    POLICY_NAME = 'ImagesAllowedForUrls'
    URL_HOST = 'http://localhost'
    URL_PORT = 8080
    URL_BASE = '%s:%d' % (URL_HOST, URL_PORT)
    URL_PAGE = '/kittens.html'
    TEST_URL = URL_BASE + URL_PAGE
    MINIMUM_IMAGE_WIDTH = 640

    URL1_DATA = [URL_HOST]
    URL2_DATA = ['http://www.bing.com', 'https://www.yahoo.com']
    URL3_DATA = ['http://www.bing.com', URL_BASE,
                 'https://www.yahoo.com']

    TEST_CASES = {
        'NotSet_Blocked': None,
        '1Url_Allowed': URL1_DATA,
        '2Urls_Blocked': URL2_DATA,
        '3Urls_Allowed': URL3_DATA
    }

    STARTUP_URLS = ['chrome://policy', 'chrome://settings']
    SUPPORTING_POLICIES = {
        'DefaultImagesSetting': 2,
        'BookmarkBarEnabled': False,
        'RestoreOnStartupURLs': STARTUP_URLS,
        'RestoreOnStartup': 4
    }

    def initialize(self, args=()):
        super(policy_ImagesAllowedForUrls, self).initialize(args)
        self.start_webserver(self.URL_PORT)

    def _wait_for_page_ready(self, tab):
        utils.poll_for_condition(
            lambda: tab.EvaluateJavaScript('pageReady'),
            exception=error.TestError('Test page is not ready.'))

    def _is_image_blocked(self, tab):
        image_width = tab.EvaluateJavaScript(
            "document.getElementById('kittens_id').width")
        return image_width < self.MINIMUM_IMAGE_WIDTH

    def _test_images_allowed_for_urls(self, policy_value, policies_dict):
        """Verify CrOS enforces the ImagesAllowedForUrls policy.

        When ImagesAllowedForUrls is undefined, images shall be blocked on
        all pages. When ImagesAllowedForUrls contains one or more URLs, images
        shall be shown only on the pages whose domain matches any of the
        listed domains.

        @param policy_value: policy value expected on chrome://policy page.
        @param policies_dict: policy dict data to send to the fake DM server.

        """
        logging.info('Running _test_images_allowed_for_urls(%s, %s)',
                     policy_value, policies_dict)
        self.setup_case(self.POLICY_NAME, policy_value, policies_dict)

        tab = self.navigate_to_url(self.TEST_URL)
        self._wait_for_page_ready(tab)
        image_is_blocked = self._is_image_blocked(tab)

        # String |URL_HOST| shall be found in string |policy_value| for test
        # cases 1Url_Allowed and 3Urls_Allowed, but not for NotSet_Blocked and
        # 2Urls_Blocked.
        if policy_value is not None and self.URL_HOST in policy_value:
            if image_is_blocked:
                raise error.TestFail('Image should not be blocked.')
        else:
            if not image_is_blocked:
                raise error.TestFail('Image should be blocked.')
        tab.Close()

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
        self._test_images_allowed_for_urls(policy_value, policies_dict)
