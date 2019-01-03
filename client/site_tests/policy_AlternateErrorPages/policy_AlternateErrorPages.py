# Copyright 2018 The Chromium OS Authors. All rights reserved.
# Use of this source code is governed by a BSD-style license that can be
# found in the LICENSE file.

import time

from autotest_lib.client.common_lib import error
from autotest_lib.client.cros.enterprise import enterprise_policy_base


class policy_AlternateErrorPages(
        enterprise_policy_base.EnterprisePolicyTest):
    """
    Test effect of policy_AlternateErrorPages policy on Chrome OS.

    """
    version = 1

    POLICY_NAME = 'AlternateErrorPagesEnabled'
    SUGGESTED = 'Did you mean http://localhost-8080.com/?'
    RESULTS_DICT = {
        True: SUGGESTED,
        False: 'Checking the connection',
        None: SUGGESTED}

    def _alt_page_check(self, policy_value):
        """
        Navigates to an invalid webpage, then checks the first item of the
        suggestion list.

        @param policy_value: bool or None, the setting of the policy.

        """
        search_box = '#suggestions-list li'
        tab = self.navigate_to_url('http://localhost:8080/')

        # Wait for the page to load before checking it
        tab.WaitForFrameToBeDisplayed(1)
        list_content = tab.EvaluateJavaScript(
            "document.querySelector('{}').innerText"
            .format(search_box))

        if self.RESULTS_DICT[policy_value] != list_content:
            raise error.TestFail(
                'AlternateErrorPage was not set! Expected the first item in'
                ' the suggestions-list to be "{}" but received "{}"'
                .format(self.RESULTS_DICT[policy_value], list_content))

    def run_once(self, case):
        """
        @param case: Name of the test case to run.

        """
        self.setup_case(user_policies={self.POLICY_NAME: case})
        self._alt_page_check(case)
