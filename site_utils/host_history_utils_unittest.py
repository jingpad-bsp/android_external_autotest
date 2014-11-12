# Copyright (c) 2014 The Chromium OS Authors. All rights reserved.
# Use of this source code is governed by a BSD-style license that can be
# found in the LICENSE file.

import collections

import common
from autotest_lib.client.common_lib.test_utils import unittest
from autotest_lib.site_utils import host_history_utils

class HostHistoryUtilsTests(unittest.TestCase):
    """Test functions in host_history_utils.
    """

    def testCalculateStatusTimes(self):
        """Test function calculate_status_times.
        """
        locked_intervals = [(2, 4), (4, 8)]
        results = host_history_utils.calculate_status_times(
                t_start=0, t_end=10, int_status='Ready', metadata={},
                locked_intervals=locked_intervals)
        expected = collections.OrderedDict(
                [((0, 4), {'status': 'Locked', 'metadata': {}}),
                 ((4, 8), {'status': 'Locked', 'metadata': {}}),
                 ((8, 10), {'status': 'Ready', 'metadata': {}})])
        self.assertEqual(results, expected)

        locked_intervals = [(0, 4), (11, 14), (16, 18)]
        results = host_history_utils.calculate_status_times(
                t_start=10, t_end=15, int_status='Ready', metadata={},
                locked_intervals=locked_intervals)
        expected = collections.OrderedDict(
                [((10, 14), {'status': 'Locked', 'metadata': {}}),
                 ((14, 15), {'status': 'Ready', 'metadata': {}})])
        self.assertEqual(results, expected)

        locked_intervals = [(2, 4), (4, 8)]
        results = host_history_utils.calculate_status_times(
                t_start=0, t_end=10, int_status='Running', metadata={},
                locked_intervals=locked_intervals)
        expected = collections.OrderedDict(
                [((0, 10), {'status': 'Running', 'metadata': {}})])
        self.assertEqual(results, expected)


if __name__ == '__main__':
    unittest.main()
