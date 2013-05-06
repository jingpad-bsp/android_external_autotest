# Copyright (c) 2013 The Chromium OS Authors. All rights reserved.
# Use of this source code is governed by a BSD-style license that can be
# found in the LICENSE file.

"""This module contains unit tests for firmware_summary module."""


import os
import unittest

import common_unittest_utils

from firmware_constants import VAL
from firmware_summary import FirmwareSummary


# Define the relative segment weights of a validator.
segment_weight = {VAL.BEGIN: 0.15,
                  VAL.MIDDLE: 0.7,
                  VAL.END: 0.15,
                  VAL.BOTH_ENDS: 0.15 + 0.15,
                  VAL.WHOLE: 0.15 + 0.7 + 0.15}

# Define the validator score weights
weight_rare = 1
weight_common = 2
weight_critical = 3
validator_weight = {'CountPacketsValidator': weight_common,
                    'CountTrackingIDValidator': weight_critical,
                    'DrumrollValidator': weight_rare,
                    'LinearityValidator': weight_common,
                    'NoGapValidator': weight_common,
                    'NoLevelJumpValidator': weight_rare,
                    'NoReversedMotionValidator': weight_common,
                    'PhysicalClickValidator': weight_critical,
                    'PinchValidator': weight_common,
                    'RangeValidator': weight_common,
                    'ReportRateValidator': weight_common,
                    'StationaryFingerValidator': weight_common}


class FirmwareSummaryTest(unittest.TestCase):
    """A base class for FirwareSummary unit tests."""
    @classmethod
    def setUpClass(cls):
        test_dir = os.path.join(os.getcwd(), 'tests')
        log_dir = os.path.join(test_dir, 'logs', cls.log_category)
        summary = FirmwareSummary(log_dir=log_dir,
                                  validator_weight=validator_weight,
                                  segment_weight=segment_weight)
        cls._validator_average = summary.validator_average
        cls._validator_ssd = summary.validator_ssd
        cls._validator_summary_score = summary.validator_summary_score
        cls._validator_summary_ssd = summary.validator_summary_ssd
        cls._weighted_average = summary.weighted_average
        cls._round_digits = 8

    def _get_score(self, fw, validator, gesture):
        """Score = sum / count, rounded to the 4th digit."""
        return round(self._validator_average[fw][validator][gesture],
                     self._round_digits)


class FirmwareSummaryLumpyTest(FirmwareSummaryTest):
    """Unit tests for firmware_summary.FirmwareSummary class using Lumpy logs.

    Tests were conducted with both fw 11.23 and 11.26, and in combination of
    single and multiple iterations.
    """
    @classmethod
    def setUpClass(cls):
        cls.log_category = 'lumpy'
        cls.fws = ['fw_11.23', 'fw_11.27']
        super(FirmwareSummaryLumpyTest, cls).setUpClass()

    def _test_by_gesture(self, validator, expected_scores):
        for fw, fw_expected_scores in expected_scores.items():
            for gesture, expected_score in fw_expected_scores.items():
                actual_score = self._get_score(fw, validator, gesture)
                self.assertAlmostEqual(actual_score, expected_score)

    def test_by_gesture_LinearityBothEndsValidator(self):
        validator = 'Linearity(BothEnds)Validator'
        expected_scores = {
            'fw_11.23': {
                'one_finger_tracking': 0.67842352,
                'two_finger_tracking': 0.79016602,
                'one_finger_to_edge': 0.67996557,
            },
            'fw_11.27': {
                'one_finger_tracking': 0.87874238,
                'two_finger_tracking': 0.80599838,
                'one_finger_to_edge': 0.79936714,
            }
        }
        self._test_by_gesture(validator, expected_scores)

    def test_by_gesture_LinearityMiddleValidator(self):
        validator = 'Linearity(Middle)Validator'
        expected_scores = {
            'fw_11.23': {
                'one_finger_tracking': 0.72945338,
                'two_finger_tracking': 0.91632697,
                'one_finger_to_edge': 0.92356771,
            },
            'fw_11.27': {
                'one_finger_tracking': 0.84746010,
                'two_finger_tracking': 0.99998892,
                'one_finger_to_edge': 0.66666667,
            }
        }
        self._test_by_gesture(validator, expected_scores)

    def test_by_gesture_NoGapValidator(self):
        validator = 'NoGapValidator'
        expected_scores = {
            'fw_11.23': {
                'one_finger_tracking': 0.11006574,
                'two_finger_tracking': 0.09455679,
                'one_finger_to_edge': 0.16022362,
            },
            'fw_11.27': {
                'one_finger_tracking': 0.86488696,
                'two_finger_tracking': 0.76206434,
                'one_finger_to_edge': 0.00000000,
            }
        }
        self._test_by_gesture(validator, expected_scores)

    def test_by_validator(self):
        validator = 'CountTrackingIDValidator'
        expected_scores = {
            'fw_11.23': {
                'Linearity(BothEnds)Validator': 0.74249667,
                'Linearity(Middle)Validator': 0.86396891,
                'NoGapValidator': 0.10836890,
            },
            'fw_11.27': {
                'Linearity(BothEnds)Validator': 0.82583506,
                'Linearity(Middle)Validator': 0.90879180,
                'NoGapValidator': 0.68257590,
            }
        }
        for fw, fw_expected_scores in expected_scores.items():
            for validator, expected_score in fw_expected_scores.items():
                actual_score = self._validator_summary_score[validator][fw]
                actual_score = round(actual_score, self._round_digits)
                self.assertAlmostEqual(actual_score, expected_score)

    def test_final_weighted_average(self):
        expected_weighted_averages = {
            'fw_11.23': 0.83536569,
            'fw_11.27': 0.93257017,
        }
        for fw, expected_value in expected_weighted_averages.items():
            actual_value = self._weighted_average[fw]
            actual_value = round(actual_value, self._round_digits)
            self.assertAlmostEqual(actual_value, expected_value)


if __name__ == '__main__':
  unittest.main()
