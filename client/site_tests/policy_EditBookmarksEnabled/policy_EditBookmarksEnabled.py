# Copyright 2015 The Chromium OS Authors. All rights reserved.
# Use of this source code is governed by a BSD-style license that can be
# found in the LICENSE file.

import logging
import time

from autotest_lib.client.common_lib import error
from autotest_lib.client.cros import enterprise_policy_base


class policy_EditBookmarksEnabled(enterprise_policy_base.EnterprisePolicyTest):
    """Test effect of EditBookmarksEnabled policy on Chrome OS behavior.

    This test verifies the behavior of Chrome OS for all valid values of the
    EditBookmarksEnabled user policy: True, False, and not set. 'Not set'
    means that the policy value is undefined. This usually induces the
    default behavior, equivalent to what is seen by an un-managed user or
    device.

    When set True or 'Not set', bookmarks can be added, removed, or modified.
    When set False, bookmarks cannot be added, removed, or modified, though
    existing bookmarks (if any) are still available.

    """
    version = 1

    POLICY_NAME = 'EditBookmarksEnabled'
    BOOKMARKS = """
        [
          {
            "name": "Google",
            "url": "https://www.google.com/"
          },
          {
            "name": "CNN",
            "url": "http://www.cnn.com/"
          },
          {
            "name": "IRS",
            "url": "http://www.irs.gov/"
          }
        ]
      """
    SUPPORTING_POLICIES = {
        'BookmarkBarEnabled': True,
        'ManagedBookmarks': BOOKMARKS
    }

    # List of named test cases.
    TEST_CASES = {
        'True': 'true',
        'False': 'false',
        'NotSet': None
    }

    def _test_edit_bookmarks_enabled(self, policy_value, policies_json):
        """
        Verify CrOS enforces EditBookmarksEnabled policy.

        When EditBookmarksEnabled is true or not set, the UI allows the user
        to add bookmarks. When false, the UI does not allow the user to add
        bookmarks.

        Warning: Non-intuitively, when the 'Bookmark Editing' setting on the
        CPanel User Settings is chosen as 'Enable bookmark editing', then the
        EditBookmarksEnabled policy on the client will be set to None. Thus,
        when verifying the 'Enable bookmark editing' choice from a production
        or staging DMS, use case=NotSet.

        @param policy_value: policy value expected on chrome://policy page.
        @param policies_json: policy JSON data to send to the fake DM server.

        """
        self.setup_case(self.POLICY_NAME, policy_value, policies_json)
        logging.info('Running _test_edit_bookmarks_enabled(%s, %s)',
                     policy_value, policies_json)
        if policy_value == 'true' or policy_value is None:
            if self._is_add_bookmark_disabled():
                raise error.TestFail('Add Bookmark should be enabled.')
        else:
            if not self._is_add_bookmark_disabled():
                raise error.TestFail('Add Bookmark should be disabled.')

    def _is_add_bookmark_disabled(self):
        """
        Check whether add-new-bookmark-command menu item is disabled.

        @returns: True if add-new-bookmarks-command is disabled.

        """
        tab = self.cr.browser.tabs.New()
        tab.Navigate('chrome://bookmarks/#1')
        tab.WaitForDocumentReadyStateToBeComplete()

        # Wait until list.reload() is defined on bmm page.
        tab.WaitForJavaScriptExpression(
            "typeof bmm.list.reload == 'function'", 60)
        time.sleep(1)  # Allow JS to run after function is defined.

        # Check if add-new-bookmark menu command has disabled property.
        is_disabled = tab.EvaluateJavaScript(
            '$("add-new-bookmark-command").disabled;')
        logging.info('add-new-bookmark-command is disabled: %s', is_disabled)
        tab.Close()
        return is_disabled

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

        # If |value| was given by user, then set expected |policy_value| to
        # the given value, and setup |policies_json| to None.
        if self.is_value_given:
            policy_value = self.value
            policies_json = None

        # Otherwise, set expected |policy_value| and setup |policies_json|
        # data to the defaults required by the test |case|.
        else:
            policy_value = self.TEST_CASES[case]
            policies_json = self.SUPPORTING_POLICIES.copy()
            if case == 'True':
                policy_json = {'EditBookmarksEnabled': True}
            elif case == 'False':
                policy_json = {'EditBookmarksEnabled': False}
            elif case == 'NotSet':
                policy_json = {'EditBookmarksEnabled': None}
            policies_json.update(policy_json)

        # Run test using values configured for the test case.
        self._test_edit_bookmarks_enabled(policy_value, policies_json)

    def run_once(self):
        """Main runner for the test cases."""
        if self.mode == 'all':
            for case in self.TEST_CASES:
                self._run_test_case(case)
        elif self.mode == 'single':
            self._run_test_case(self.case)
        elif self.mode == 'list':
            logging.info('List Test Cases:')
            for case, value in self.TEST_CASES.items():
                logging.info('  case=%s, value="%s"', case, value)
        else:
            raise error.TestError('Run mode %s is not valid.' % self.mode)

