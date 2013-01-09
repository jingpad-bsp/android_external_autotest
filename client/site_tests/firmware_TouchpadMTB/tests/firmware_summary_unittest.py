# Copyright (c) 2012 The Chromium OS Authors. All rights reserved.
# Use of this source code is governed by a BSD-style license that can be
# found in the LICENSE file.
#
# This module contains unit tests for the classes in the mtb module

import os
import unittest

import common_unittest_utils
import firmware_summary


class FirmwareSummaryTest(unittest.TestCase):
    """Unit tests for firmware_summary.FirmwareSummary class."""

    def setUp(self):
        self._test_dir = os.path.join(os.getcwd(), 'tests')
        self._log_dir = os.path.join(self._test_dir, 'logs')
        summary = firmware_summary.FirmwareSummary(log_dir=self._log_dir)
        self._validator_average = summary.validator_average
        self._validator_ssd = summary.validator_ssd
        self._validator_summary_score = summary.validator_summary_score
        self._validator_summary_ssd = summary.validator_summary_ssd
        self.fws = ['fw_11.26', 'fw_11.23']
        self._round_digits = 4

    def _get_score(self, fw, validator, gesture):
        """Score = sum / count, rounded to the 4th digit."""
        return round(self._validator_average[fw][validator][gesture],
                     self._round_digits)

    def _get_ssd(self, fw, validator, gesture):
        """Get the sample standard deviation rounded to the 4th digit."""
        return round(self._validator_ssd[fw][validator][gesture],
                     self._round_digits)

    def test_combine_rounds_NoGapValidator(self):
        validator = 'NoGapValidator'
        gestures = [
            'one_finger_tracking',
            'two_finger_tracking',
            'one_finger_to_edge',
            'finger_crossing'
        ]
        # The following expected_scores were calculated by hand.
        expected_scores = {
            'fw_11.26': {
                'one_finger_tracking': 0.9806,
                'two_finger_tracking': 0.9827,
                'one_finger_to_edge': 0.6934,
                'finger_crossing': 0.7710,
            },
            'fw_11.23': {
                'one_finger_tracking': 0.5012,
                'two_finger_tracking': 0.5623,
                'one_finger_to_edge': 0.2948,
                'finger_crossing': 0.9165,
            }
        }
        for gesture in gestures:
            for fw in self.fws:
                actual_score = self._get_score(fw, validator, gesture)
                expected_score = expected_scores[fw][gesture]
                self.assertAlmostEqual(actual_score, expected_score)

    def test_combine_gestures_NoGapValidator(self):
        validator = 'NoGapValidator'
        # The following expected_scores were calculated by hand.
        expected_scores = {
            'fw_11.26': 0.8821,
            'fw_11.23': 0.5674,
        }
        for fw in self.fws:
            actual_score_original = self._validator_summary_score[validator][fw]
            actual_score = round(actual_score_original, self._round_digits)
            expected_score = expected_scores[fw]
            self.assertAlmostEqual(actual_score, expected_score)

    def test_combine_rounds_CountTrackingIDValidator(self):
        validator = 'CountTrackingIDValidator'
        gestures = ['one_finger_tracking',]
        # The following expected_scores were calculated by hand.
        expected_scores = {
            'fw_11.26': {'one_finger_tracking': 1.0,},
            'fw_11.23': {'one_finger_tracking': 0.75,},
        }
        for gesture in gestures:
            for fw in self.fws:
                actual_score = self._get_score(fw, validator, gesture)
                expected_score = expected_scores[fw][gesture]
                self.assertAlmostEqual(actual_score, expected_score)

    def test_combine_gestures_CountTrackingIDValidator(self):
        validator = 'CountTrackingIDValidator'
        # The following expected_scores were calculated by hand.
        expected_scores = {
            'fw_11.26': 1.0,
            'fw_11.23': 0.9583,
        }
        for fw in self.fws:
            actual_score_original = self._validator_summary_score[validator][fw]
            actual_score = round(actual_score_original, self._round_digits)
            expected_score = expected_scores[fw]
            self.assertAlmostEqual(actual_score, expected_score)

    def _test_summary_by_gesture_ssd(self, validator, gestures, expected_dict):
        for gesture in gestures:
            for fw in self.fws:
                actual_value = self._get_ssd(fw, validator, gesture)
                expected_value = expected_dict[fw][gesture]
                self.assertAlmostEqual(actual_value, expected_value)

    def test_summary_by_gesture_ssd_CountTrackingIDValidator(self):
        validator = 'CountTrackingIDValidator'
        gestures = ['one_finger_tracking',]
        # The following expected_scores were calculated by hand.
        expected_ssd = {
            'fw_11.26': {'one_finger_tracking': 0.0000},
            'fw_11.23': {'one_finger_tracking': 0.5000},
        }
        self._test_summary_by_gesture_ssd(validator, gestures, expected_ssd)

    def test_summary_by_gesture_ssd_LinearityBothEndsValidator(self):
        validator = 'LinearityBothEndsValidator'
        gestures = ['two_finger_tracking',]
        # The following expected_scores were calculated by hand.
        expected_ssd = {
            'fw_11.26': {'two_finger_tracking': 0.2743},
            'fw_11.23': {'two_finger_tracking': 0.1456},
        }
        self._test_summary_by_gesture_ssd(validator, gestures, expected_ssd)

    def test_summary_by_validator_ssd_LinearityBothEndsValidator(self):
        validator = 'LinearityBothEndsValidator'
        # The following expected_scores were calculated by hand.
        expected_ssd = {
            'fw_11.26': 0.2600,
            'fw_11.23': 0.1173,
        }
        for fw in self.fws:
            actual_value_original = self._validator_summary_ssd[validator][fw]
            actual_value = round(actual_value_original, self._round_digits)
            expected_value = expected_ssd[fw]
            self.assertAlmostEqual(actual_value, expected_value)


if __name__ == '__main__':
  unittest.main()
