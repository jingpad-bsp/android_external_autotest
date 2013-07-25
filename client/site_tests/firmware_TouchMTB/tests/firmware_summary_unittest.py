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
segment_weights = {VAL.BEGIN: 0.15,
                   VAL.MIDDLE: 0.7,
                   VAL.END: 0.15,
                   VAL.BOTH_ENDS: 0.15 + 0.15,
                   VAL.WHOLE: 0.15 + 0.7 + 0.15}

# Define the validator score weights
weight_rare = 1
weight_common = 2
weight_critical = 3
validator_weights = {'CountPacketsValidator': weight_common,
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
                                  validator_weights=validator_weights,
                                  segment_weights=segment_weights)
        cls.slog = summary.slog
        cls._round_digits = 8

    def _get_score(self, fw=None, gesture=None, validator=None):
        """Score = sum / count, rounded to the 4th digit."""
        result= self.slog.get_result(fw=fw, gesture=gesture,
                                     validator=validator)
        average = result.stat_scores.average
        return round(average, self._round_digits)


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
                actual_score = self._get_score(fw=fw,
                                               gesture=gesture,
                                               validator=validator)
                self.assertAlmostEqual(actual_score, expected_score)

    def test_by_gesture_CountTrackingIDValidator(self):
        validator = 'CountTrackingIDValidator'
        expected_scores = {
            'fw_11.23': {
                'drag_edge_thumb': 0.0,
                'one_finger_tracking': 1.0,
                'two_finger_tracking': 1.0,
            },
            'fw_11.27': {
                'drag_edge_thumb': 0.5,
                'one_finger_tracking': 1.0,
                'two_finger_tracking': 1.0,
            }
        }
        self._test_by_gesture(validator, expected_scores)

    def test_by_gesture_DrumrollValidator(self):
        validator = 'DrumrollValidator'
        expected_scores = {
            'fw_11.23': {
                'drumroll': 0.75,
            },
            'fw_11.27': {
                'drumroll': 0.66666667,
            }
        }
        self._test_by_gesture(validator, expected_scores)

    def test_by_gesture_LinearityBothEndsValidator(self):
        validator = 'Linearity(BothEnds)Validator'
        expected_scores = {
            'fw_11.23': {
                'one_finger_to_edge': 0.0,
                'one_finger_tracking': 0.0463055176218,
                'two_finger_tracking': 0.0675201120507,
            },
            'fw_11.27': {
                'one_finger_to_edge': 0.0,
                'one_finger_tracking': 0.0307156362557,
                'two_finger_tracking': 0.018688307809,
            }
        }
        self._test_by_gesture(validator, expected_scores)

    def test_by_gesture_LinearityMiddleValidator(self):
        validator = 'Linearity(Middle)Validator'
        expected_scores = {
            'fw_11.23': {
                'one_finger_to_edge': 0.0,
                'one_finger_tracking': 0.141366526226,
                'two_finger_tracking': 0.374448984788,
            },
            'fw_11.27': {
                'one_finger_to_edge': 0.104395042218,
                'one_finger_tracking': 0.180251899598,
                'two_finger_tracking': 0.414553692112,
            }
        }
        self._test_by_gesture(validator, expected_scores)

    def test_by_gesture_NoGapValidator(self):
        validator = 'NoGapValidator'
        expected_scores = {
            'fw_11.23': {
                'one_finger_to_edge': 0.16022362,
                'one_finger_tracking': 0.11006574,
                'two_finger_tracking': 0.09455679,
            },
            'fw_11.27': {
                'one_finger_to_edge': 0.00000000,
                'one_finger_tracking': 0.86488696,
                'two_finger_tracking': 0.76206434,
            }
        }
        self._test_by_gesture(validator, expected_scores)

    def test_by_gesture_PhysicalClickValidator(self):
        validator = 'PhysicalClickValidator'
        expected_scores = {
            'fw_11.23': {
                'one_finger_physical_click': 0.875,
                'two_fingers_physical_click': 0.25,
            },
            'fw_11.27': {
                'one_finger_physical_click': 1.0,
                'two_fingers_physical_click': 1.0,
            }
        }
        self._test_by_gesture(validator, expected_scores)

    def test_by_gesture_StationaryFingerValidator(self):
        validator = 'StationaryFingerValidator'
        expected_scores = {
            'fw_11.23': {
                'one_finger_physical_click': 0.748714663186,
                'two_fingers_physical_click': 1.0,
            },
            'fw_11.27': {
                'one_finger_physical_click': 0.891563952369,
                'two_fingers_physical_click': 1.0,
            }
        }
        self._test_by_gesture(validator, expected_scores)

    def test_by_validator(self):
        expected_scores = {
            'fw_11.23': {
                'CountTrackingIDValidator': 0.962962962963,
                'CountPacketsValidator': 0.895833333333,
                'DrumrollValidator': 0.75,
                'Linearity(BothEnds)Validator': 0.0483588644595,
                'Linearity(Middle)Validator': 0.239845374323,
                'NoGapValidator': 0.101144302433,
                'PhysicalClickValidator': 0.75,
                'StationaryFingerValidator': 0.832476442124,
            },
            'fw_11.27': {
                'CountTrackingIDValidator': 0.975609756098,
                'CountPacketsValidator': 1.0,
                'DrumrollValidator': 0.666666666667,
                'Linearity(BothEnds)Validator': 0.017763196141,
                'Linearity(Middle)Validator': 0.313444723824,
                'NoGapValidator': 0.623221473233,
                'PhysicalClickValidator': 1.0,
                'StationaryFingerValidator': 0.92770930158,
            }
        }
        for fw, fw_expected_scores in expected_scores.items():
            for validator, expected_score in fw_expected_scores.items():
                actual_score = self._get_score(fw=fw, validator=validator)
                actual_score = round(actual_score, self._round_digits)
                self.assertAlmostEqual(actual_score, expected_score)

    def test_stat_metrics(self):
        """Test the statistics of metrics."""
        expected_stats_values = {
            'fw_11.23': {
                'CountPacketsValidator':
                    [('pct of incorrect cases (%)-packets', 25.00)],
            },
            'fw_11.27': {
                'CountPacketsValidator':
                    [('pct of incorrect cases (%)-packets', 0.00)],
            },
        }

        for fw, fw_stats_values in expected_stats_values.items():
            for validator, stats_metrics in fw_stats_values.items():
                result = self.slog.get_result(fw=fw, validator=validator)
                for metric_name, expected_value in stats_metrics:
                    actual_value = result.stat_metrics.stats_values[metric_name]
                    self.assertAlmostEqual(actual_value, expected_value)

    def test_final_weighted_average(self):
        expected_weighted_averages = {
            'fw_11.23': 0.7266936870585381,
            'fw_11.27': 0.8499773935896175,
        }
        final_weighted_average = self.slog.get_final_weighted_average()
        for fw, expected_value in expected_weighted_averages.items():
            actual_value = final_weighted_average[fw]
            actual_value = round(actual_value, self._round_digits)
            self.assertAlmostEqual(actual_value, expected_value)


if __name__ == '__main__':
  unittest.main()
