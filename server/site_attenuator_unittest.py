#!/usr/bin/python
#
# Copyright (c) 2013 The Chromium OS Authors. All rights reserved.
# Use of this source code is governed by a BSD-style license that can be
# found in the LICENSE file.

"""Unit tests for server/site_attenuator.py."""

import unittest

from autotest_lib.server import site_attenuator


class ApproximateFrequencyTest(unittest.TestCase):
    """Unit tests for site_attenuator._approximate_frequency()."""

    def _run(self, test_freq, expected):
        actual = site_attenuator.Attenuator._approximate_frequency(test_freq)
        self.assertEquals(actual, expected)


    def testApproximateFrequency_2GhzReturnsHigherValue(self):
        """Tests a higher frequency is returned as an approximate in 2GHz."""
        self._run(2412, 2437)  # Channel 1. Expect return of channel 6


    def testApproximateFrequency_2GhzReturnsLowerValue(self):
        """Tests a lower frequency is returned as an approximate in 2GHz."""
        self._run(2462, 2437)  # Channel 11. Expect return of channel 6


    def testApproximateFrequency_5GhzReturnsHigherValue(self):
        """Tests a higher frequency is returned as an approximate in 5GHz."""
        self._run(5200, 5220)  # Channel 40. Expect return of channel 44

    def testApproximateFrequency_5GhzReturnsLowerValue(self):
        """Tests a lower frequency is returned as an approximate in 5GHz."""
        self._run(5785, 5765)  # Channel 157. Expect return of channel 153
