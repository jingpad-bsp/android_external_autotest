# Copyright 2015 The Chromium OS Authors. All rights reserved.
# Use of this source code is governed by a BSD-style license that can be
# found in the LICENSE file.

import logging

from autotest_lib.client.common_lib import error
from autotest_lib.client.cros import enterprise_policy_base


class policy_EditBookmarksEnabled(enterprise_policy_base.EnterprisePolicyTest):
    """Test effect of EditBookmarksEnabled policy on Chrome OS behavior.

    This test verifies the behavior of Chrome OS for all valid values of the
    EditBookmarksEnabled user policy: True, False, and not set. 'Not set'
    means that the policy value is un-defined. This usually induces the
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
            "url": "https://google.com"
          },
          {
            "name": "CNN",
            "url": "http://cnn.com"
          },
          {
            "name": "IRS",
            "url": "www.irs.com"
          }
        ]
      """

    # List of named test cases.
    TEST_CASES = ['True', 'False', 'NotSet']

    def initialize(self, args=()):
        super(policy_EditBookmarksEnabled, self).initialize(args)

    def _test_SetTrueOrNotSet(self, policy_value):
        """Test with EditBookmarksEnabled set true or not set.

        When EditBookmarksEnabled is true or not set, the user is able to add,
        remove, and edit bookmarks.

        @param policy_value: policy value expected to be shown on
        chrome://policy page.
        """
        # Setup policies JSON data for test.
        if policy_value == 'true':
            policies_json = {'EditBookmarksEnabled': True,
                             'BookmarkBarEnabled': True,
                             'ManagedBookmarks': self.BOOKMARKS
                            }
        else:
            policies_json = {'EditBookmarksEnabled': None,
                             'BookmarkBarEnabled': True,
                             'ManagedBookmarks': self.BOOKMARKS
                            }
        self.setup_case(self.POLICY_NAME, policy_value, policies_json)

        # Insert procedure below to test EditBookmarksEnabled set true,
        # or not set. Expected behavior is the same for both settings.
        # Dummy procedure for debugging purposes. Remove before commit.
        logging.info('test_TrueOrNotSet(%s)', policy_value)

    def _test_SetFalse(self, policy_value):
        """Test with EditBookmarksEnabled set false.

        When EditBookmarksEnabled is false, the user is not able to add,
        remove, or edit bookmarks. However, existing bookmarks are still
        shown and may be used.

        @param policy_value: policy value expected to be shown on
        chrome://policy page.
        """
        # Setup policies JSON data for test.
        policies_json = {'EditBookmarksEnabled': False,
                         'BookmarkBarEnabled': True,
                         'ManagedBookmarks': self.BOOKMARKS
                        }
        self.setup_case(self.POLICY_NAME, policy_value, policies_json)

        # Insert procedure below to test EditBookmarksEnabled set false.
        # Dummy procedure for debugging purposes. Remove before commit.
        logging.info('test_SetFalse(%s)', policy_value)

    def _run_test_case(self, case):
        """Run the test case given by |case|.

        @param case: Name of the test case to run.
        """
        logging.info('self.value: %s', self.value)
        if case == 'True':
            policy_value = self.value or 'true'
            self._test_SetTrueOrNotSet(policy_value)
        elif case == 'False':
            policy_value = self.value or 'false'
            self._test_SetFalse(policy_value)
        elif case == 'NotSet':
            policy_value = self.value or None
            self._test_SetTrueOrNotSet(policy_value)
        else:
            raise error.TestError('Test case %s is not valid.' % case)

    def run_once(self):
        """Main runner for the test cases."""
        if self.mode == 'all':
            # Run all test case methods.
            for case in self.TEST_CASES:
                self._run_test_case(case)
        elif self.mode == 'single':
            # Run the user-specified |case| method.
            self._run_test_case(self.case)
        elif self.mode == 'list':
            # List all test cases.
            logging.info('List Test Cases:')
            for case in self.TEST_CASES:
                logging.info('  %s', case)
        else:
            raise error.TestError('Run mode %s is not valid.' % self.mode)

