# Copyright (c) 2012 The Chromium OS Authors. All rights reserved.
# Use of this source code is governed by a BSD-style license that can be
# found in the LICENSE file.
#

"""This module contains unit tests for the classes in the validators module."""

import glob
import os.path
import unittest

import common_unittest_utils
import common_util
import test_conf as conf
import validators

from common_unittest_utils import create_mocked_devices, parse_tests_data
from firmware_constants import GV, PLATFORM
from firmware_log import MetricNameProps
from touch_device import TouchDevice
from validators import (CountPacketsValidator,
                        CountTrackingIDValidator,
                        DrumrollValidator,
                        LinearityValidator,
                        NoGapValidator,
                        NoLevelJumpValidator,
                        NoReversedMotionValidator,
                        PhysicalClickValidator,
                        PinchValidator,
                        RangeValidator,
                        ReportRateValidator,
                        StationaryFingerValidator,
)


unittest_path_lumpy = os.path.join(os.getcwd(), 'tests/logs/lumpy')
mocked_device = create_mocked_devices()

# Make short aliases for supported platforms
alex = mocked_device[PLATFORM.ALEX]
lumpy = mocked_device[PLATFORM.LUMPY]
link = mocked_device[PLATFORM.LINK]
# Some tests do not care what device is used.
dontcare = 'dontcare'


class BaseValidatorTest(unittest.TestCase):
    """A base class for all ValidatorTest classes."""

    def setUp(self, show_spec_v2_flag=False):
        """Set up mocked devices for various test boards.

        @param show_spec_v2_flag: this flag indicates if we are using spec v2.
        """
        validators.set_show_spec_v2(show_spec_v2_flag)

    def tearDown(self):
        """Reset the show_spec_v2 so that other unit tests for spec v1 could be
        conducted as uaual.
        """
        validators.set_show_spec_v2(False)


class CountTrackingIDValidatorTest(BaseValidatorTest):
    """Unit tests for CountTrackingIDValidator class."""

    def setUp(self):
        super(CountTrackingIDValidatorTest, self).setUp()

    def _test_count_tracking_id(self, filename, criteria, device):
        packets = parse_tests_data(filename)
        validator = CountTrackingIDValidator(criteria, device=device)
        vlog = validator.check(packets)
        return vlog.score

    def test_two_finger_id_change(self):
        """Two two fingers id change.

        Issue 7867: Cyapa : Two finger scroll, tracking ids change
        """
        filename = 'two_finger_id_change.dat'
        score = self._test_count_tracking_id(filename, '== 2', lumpy)
        self.assertTrue(score == 0)

    def test_one_finger_fast_swipe_id_split(self):
        """One finger fast swipe resulting in IDs split.

        Issue: 7869: Lumpy: Tracking ID reassigned during quick-2F-swipe
        """
        filename = 'one_finger_fast_swipe_id_split.dat'
        score = self._test_count_tracking_id(filename, '== 1', lumpy)
        self.assertTrue(score == 0)

    def test_two_fingers_fast_flick_id_split(self):
        """Two figners fast flick resulting in IDs split.

        Issue: 7869: Lumpy: Tracking ID reassigned during quick-2F-swipe
        """
        filename = 'two_finger_fast_flick_id_split.dat'
        score = self._test_count_tracking_id(filename, '== 2', lumpy)
        self.assertTrue(score == 0)


class DrumrollValidatorTest(BaseValidatorTest):
    """Unit tests for DrumrollValidator class."""

    def setUp(self):
        super(DrumrollValidatorTest, self).setUp()
        self.criteria = conf.drumroll_criteria

    def _test_drumroll(self, filename, criteria, device):
        packets = parse_tests_data(filename)
        validator = DrumrollValidator(criteria, device=device)
        vlog = validator.check(packets)
        return vlog.score

    def _get_drumroll_metrics(self, filename, criteria, device):
        packets = parse_tests_data(filename, gesture_dir=unittest_path_lumpy)
        validator = DrumrollValidator(criteria, device=device)
        metrics = validator.check(packets).metrics
        return metrics

    def test_drumroll_lumpy(self):
        """Should catch the drumroll on lumpy.

        Issue 7809: Lumpy: Drumroll bug in firmware
        Max distance: 52.02 px
        """
        filename = 'drumroll_lumpy.dat'
        score = self._test_drumroll(filename, self.criteria, lumpy)
        self.assertTrue(score == 0)

    def test_drumroll_lumpy_1(self):
        """Should catch the drumroll on lumpy.

        Issue 7809: Lumpy: Drumroll bug in firmware
        Max distance: 43.57 px
        """
        filename = 'drumroll_lumpy_1.dat'
        score = self._test_drumroll(filename, self.criteria, lumpy)
        self.assertTrue(score <= 0.15)

    def test_no_drumroll_link(self):
        """Should pass (score == 1) when there is no drumroll.

        Issue 7809: Lumpy: Drumroll bug in firmware
        Max distance: 2.92 px
        """
        filename = 'no_drumroll_link.dat'
        score = self._test_drumroll(filename, self.criteria, link)
        self.assertTrue(score == 1)

    def test_drumroll_metrics(self):
        """Test the drumroll metrics."""
        expected_max_values = {
            '20130506_030025-fw_11.27-robot_sim/'
            'drumroll.fast-lumpy-fw_11.27-manual-20130528_044804.dat':
            2.29402908535,

            '20130506_030025-fw_11.27-robot_sim/'
            'drumroll.fast-lumpy-fw_11.27-manual-20130528_044820.dat':
            0.719567771497,

            '20130506_031746-fw_11.27-robot_sim/'
            'drumroll.fast-lumpy-fw_11.27-manual-20130528_044728.dat':
            0.833491481592,

            '20130506_032458-fw_11.23-robot_sim/'
            'drumroll.fast-lumpy-fw_11.23-manual-20130528_044856.dat':
            1.18368539364,

            '20130506_032458-fw_11.23-robot_sim/'
            'drumroll.fast-lumpy-fw_11.23-manual-20130528_044907.dat':
            0.851161282019,

            '20130506_032659-fw_11.23-robot_sim/'
            'drumroll.fast-lumpy-fw_11.23-manual-20130528_044933.dat':
            2.64245519251,

            '20130506_032659-fw_11.23-robot_sim/'
            'drumroll.fast-lumpy-fw_11.23-manual-20130528_044947.dat':
            0.910624022916,
        }
        criteria = self.criteria
        for filename, expected_max_value in expected_max_values.items():
            metrics = self._get_drumroll_metrics(filename, criteria, lumpy)
            actual_max_value = max([m.value for m in metrics])
            self.assertAlmostEqual(expected_max_value, actual_max_value)


class LinearityValidatorTest(BaseValidatorTest):
    """Unit tests for LinearityValidator class."""

    def setUp(self):
        super(LinearityValidatorTest, self).setUp()
        self.criteria = conf.linearity_criteria
        validators.show_new_spec = False

    def _test_linearity_criteria(self, criteria_str, fingers, device):
        filename = '2f_scroll_diagonal.dat'
        direction = GV.DIAGONAL
        packets = parse_tests_data(filename)
        scores = {}
        for finger in fingers:
            validator = LinearityValidator(criteria_str, device=device,
                                           finger=finger)
            scores[finger] = validator.check(packets, direction).score
        return scores

    def test_linearity_criteria0(self):
        """The scores are 0s due to strict criteria."""
        criteria_str = '<= 0.01, ~ +0.01'
        scores = self._test_linearity_criteria(criteria_str, (0, 1), alex)
        self.assertTrue(scores[0] == 0)
        self.assertTrue(scores[1] == 0)

    def test_linearity_criteria1(self):
        """The validator gets score betwee 0 and 1."""
        criteria_str = '<= 0.01, ~ +3.0'
        scores = self._test_linearity_criteria(criteria_str, (0, 1), alex)
        self.assertTrue(scores[0] > 0 and scores[0] < 1)
        self.assertTrue(scores[1] > 0 and scores[1] < 1)

    def test_linearity_criteria2(self):
        """The validator gets score of 1 due to very relaxed criteria."""
        criteria_str = '<= 10, ~ +10'
        scores = self._test_linearity_criteria(criteria_str, (0, 1), alex)
        self.assertTrue(scores[0] == 1)
        self.assertTrue(scores[1] == 1)

    def _test_linearity_validator(self, filename, criteria, fingers, device,
                                  direction):
        packets = parse_tests_data(filename)
        scores = {}
        if isinstance(fingers, int):
            fingers = (fingers,)
        for finger in fingers:
            validator = LinearityValidator(criteria, device=device,
                                           finger=finger)
            scores[finger] = validator.check(packets, direction).score
        return scores

    def test_two_finger_jagged_lines(self):
        """Test two-finger jagged lines."""
        filename = 'two_finger_tracking.diagonal.slow.dat'
        scores = self._test_linearity_validator(filename, self.criteria, (0, 1),
                                                lumpy, GV.DIAGONAL)
        self.assertTrue(scores[0] < 0.7)
        self.assertTrue(scores[1] < 0.7)

    def test_stationary_finger_fat_finger_wobble(self):
        """Test fat finger horizontal move with a stationary resting finger
        results in a wobble.

        Issue 7551: Fat finger horizontal move with a stationary resting
        finger results in a wobble.
        """
        filename = 'stationary_finger_fat_finger_wobble.dat'
        scores = self._test_linearity_validator(filename, self.criteria, 1,
                                                lumpy, GV.HORIZONTAL)
        self.assertTrue(scores[1] <= 0.1)

    def test_thumb_edge(self):
        """Test thumb edge wobble.

        Issue 7554: thumb edge behavior.
        """
        filename = 'thumb_edge_wobble.dat'
        scores = self._test_linearity_validator(filename, self.criteria, 0,
                                                lumpy, GV.HORIZONTAL)
        self.assertTrue(scores[0] < 0.5)

    def test_two_close_fingers_merging_changed_ids_gaps(self):
        """Test close finger merging - causes id changes

        Issue 7555: close finger merging - causes id changes.
        """
        filename = 'two_close_fingers_merging_changed_ids_gaps.dat'
        scores = self._test_linearity_validator(filename, self.criteria, 0,
                                                lumpy, GV.VERTICAL)
        self.assertTrue(scores[0] < 0.3)

    def test_jagged_two_finger_scroll(self):
        """Test jagged two finger scroll.

        Issue 7650: Cyapa : poor two fat fingers horizontal scroll performance -
        jagged lines
        """
        filename = 'jagged_two_finger_scroll_horizontal.dat'
        scores = self._test_linearity_validator(filename, self.criteria, (0, 1),
                                                lumpy, GV.HORIZONTAL)
        self.assertTrue(scores[0] < 0.3)
        self.assertTrue(scores[1] < 0.3)

    def test_first_point_jump(self):
        """Test the first point jump

        At finger 0, the positions of (x, y) looks like
            x: 208, 241, 242, 245, 246, ...
            y: 551, 594, 595, 597, 598, ...
        Note that the the first y position is a jump.
        """
        filename = 'two_finger_tracking.bottom_left_to_top_right.slow.dat'
        scores = self._test_linearity_validator(filename, self.criteria, 0,
                                                lumpy, GV.DIAGONAL)
        self.assertTrue(scores[0] < 0.3)

    def test_simple_linear_regression0(self):
        validator = LinearityValidator('<= 0.2, ~ +0.3', device=lumpy, finger=0)
        validator.init_check()
        # A perfect line from bottom left to top right
        list_x = [1, 2, 3, 4, 5, 6, 7, 8]
        list_y = [20, 40, 60, 80, 100, 120, 140, 160]
        spmse = validator._simple_linear_regression(list_x, list_y)
        self.assertEqual(spmse, 0)

    def test_simple_linear_regression1(self):
        validator = LinearityValidator('<= 0.2, ~ +0.3', device=lumpy, finger=0)
        validator.init_check()
        # Another perfect line from top left to bottom right
        list_x = [1, 2, 3, 4, 5, 6, 7, 8]
        list_y = [160, 140, 120, 100, 80, 60, 40, 20]
        spmse = validator._simple_linear_regression(list_x, list_y)
        self.assertEqual(spmse, 0)

    def test_simple_linear_regression2(self):
        validator = LinearityValidator('<= 0.2, ~ +0.3', device=lumpy, finger=0)
        validator.init_check()
        # An outlier in y axis
        list_x = [1, 2, 3, 4, 5, 6, 7, 8]
        list_y = [20, 40, 60, 70, 100, 120, 140, 160]
        spmse = validator._simple_linear_regression(list_x, list_y)
        self.assertTrue(spmse > 0)

    def test_simple_linear_regression3(self):
        validator = LinearityValidator('<= 0.2, ~ +0.3', device=lumpy, finger=0)
        validator.init_check()
        # Repeated values in x axis
        list_x = [1, 2, 2, 4, 5, 6, 7, 8]
        list_y = [20, 40, 60, 80, 100, 120, 140, 160]
        spmse = validator._simple_linear_regression(list_x, list_y)
        self.assertTrue(spmse > 0)


class LinearityValidator2Test(BaseValidatorTest):
    """Unit tests for LinearityValidator2 class."""

    def setUp(self):
        super(LinearityValidator2Test, self).setUp(show_spec_v2_flag=True)
        self.validator = LinearityValidator(conf.linearity_criteria,
                                            device=lumpy, finger=0)
        self.validator.init_check()

    def test_simple_linear_regression0(self):
        """A perfect y-t line from bottom left to top right"""
        list_y = [20, 40, 60, 80, 100, 120, 140, 160]
        list_t = [i * 0.1 for i in range(len(list_y))]
        (max_err_px, rms_err_px) = self.validator._calc_errors_single_axis(
                list_t, list_y)
        self.assertAlmostEqual(max_err_px, 0)
        self.assertAlmostEqual(rms_err_px, 0)

    def test_simple_linear_regression1(self):
        """A y-t line taken from a real example.

        Refer to the "Numerical example" in the wiki page:
            http://en.wikipedia.org/wiki/Simple_linear_regression
        """
        list_t = [1.47, 1.50, 1.52, 1.55, 1.57, 1.60, 1.63, 1.65, 1.68, 1.70,
                  1.73, 1.75, 1.78, 1.80, 1.83]
        list_y = [52.21, 53.12, 54.48, 55.84, 57.20, 58.57, 59.93, 61.29,
                  63.11, 64.47, 66.28, 68.10, 69.92, 72.19, 74.46]
        expected_max_err = 1.3938545467809007
        expected_rms_err = 0.70666155991311708
        (max_err, rms_err) = self.validator._calc_errors_single_axis(
                list_t, list_y)
        self.assertAlmostEqual(max_err, expected_max_err)
        self.assertAlmostEqual(rms_err, expected_rms_err)


class NoGapValidatorTest(BaseValidatorTest):
    """Unit tests for NoGapValidator class."""
    GAPS_SUBDIR = 'gaps'

    def setUp(self):
        super(NoGapValidatorTest, self).setUp()
        self.criteria = conf.no_gap_criteria

    def _test_no_gap(self, filename, criteria, device, slot):
        file_subpath = os.path.join(self.GAPS_SUBDIR, filename)
        packets = parse_tests_data(file_subpath)
        validator = NoGapValidator(criteria, device=device, slot=slot)
        vlog = validator.check(packets)
        return vlog.score

    def test_two_finger_scroll_gaps(self):
        """Test that there are gaps in the two finger scroll gesture.

        Issue 7552: Cyapa : two finger scroll motion produces gaps in tracking
        """
        filename = 'two_finger_gaps.horizontal.dat'
        score0 = self._test_no_gap(filename, self.criteria, lumpy, 0)
        score1 = self._test_no_gap(filename, self.criteria, lumpy, 1)
        self.assertTrue(score0 <= 0.1)
        self.assertTrue(score1 <= 0.1)

    def test_gap_new_finger_arriving_or_departing(self):
        """Test gap when new finger arriving or departing.

        Issue: 8005: Cyapa : gaps appear when new finger arrives or departs
        """
        filename = 'gap_new_finger_arriving_or_departing.dat'
        score = self._test_no_gap(filename, self.criteria, lumpy, 0)
        self.assertTrue(score <= 0.3)

    def test_one_stationary_finger_2nd_finger_moving_gaps(self):
        """Test one stationary finger resulting in 2nd finger moving gaps."""
        filename = 'one_stationary_finger_2nd_finger_moving_gaps.dat'
        score = self._test_no_gap(filename, self.criteria, lumpy, 1)
        self.assertTrue(score <= 0.1)

    def test_resting_finger_2nd_finger_moving_gaps(self):
        """Test resting finger resulting in 2nd finger moving gaps.

        Issue 7648: Cyapa : Resting finger plus one finger move generates a gap
        """
        filename = 'resting_finger_2nd_finger_moving_gaps.dat'
        score = self._test_no_gap(filename, self.criteria, lumpy, 1)
        self.assertTrue(score <= 0.3)


class PhysicalClickValidatorTest(BaseValidatorTest):
    """Unit tests for PhysicalClickValidator class."""

    def setUp(self):
        super(PhysicalClickValidatorTest, self).setUp()
        self.device = lumpy
        self.criteria = '== 1'
        self.mnprops = MetricNameProps()

    def _test_physical_clicks(self, gesture_dir, files, expected_score):
        gesture_path = os.path.join(unittest_path_lumpy, gesture_dir)
        for filename, fingers in files.items():
            packets = parse_tests_data(os.path.join(gesture_path, filename))
            validator = PhysicalClickValidator(self.criteria,
                                               fingers=fingers,
                                               device=self.device)
            vlog = validator.check(packets)
            actual_score = vlog.score
            self.assertTrue(actual_score == expected_score)

    def test_physical_clicks_success(self):
        """All physcial click files in the gesture_dir should pass."""
        gesture_dir = '20130506_030025-fw_11.27-robot_sim'
        gesture_path = os.path.join(unittest_path_lumpy, gesture_dir)

        # Get all 1f physical click files.
        file_prefix = 'one_finger_physical_click'
        fingers = 1
        files1 = [(filepath, fingers) for filepath in glob.glob(
            os.path.join(gesture_path, file_prefix + '*.dat'))]

        # Get all 2f physical click files.
        file_prefix = 'two_fingers_physical_click'
        fingers = 2
        files2 = [(filepath, fingers) for filepath in glob.glob(
            os.path.join(gesture_path, file_prefix + '*.dat'))]

        # files is a dictionary of {filename: fingers}
        files = dict(files1 + files2)
        expected_score = 1.0
        self._test_physical_clicks(gesture_dir, files, expected_score)

    def test_physical_clicks_failure(self):
        """All physcial click files specified below should fail."""
        gesture_dir = '20130506_032458-fw_11.23-robot_sim'
        # files is a dictionary of {filename: fingers}
        files = {
            'one_finger_physical_click.bottom_side-lumpy-fw_11.23-complete-'
                '20130614_065744.dat': 1,
            'one_finger_physical_click.center-lumpy-fw_11.23-complete-'
                '20130614_065727.dat': 1,
            'two_fingers_physical_click-lumpy-fw_11.23-complete-'
                '20130614_065757.dat': 2,
        }
        expected_score = 0.0
        self._test_physical_clicks(gesture_dir, files, expected_score)

    def test_physical_clicks_by_finger_IDs(self):
        """Test that some physical clicks may come with or without correct
        finger IDs.
        """
        # files is a dictionary of {
        #     filename: (number_fingers, (actual clicks, expected clicks))}
        files = {
                # An incorrect case with 1 finger: the event sequence comprises
                #   Event: ABS_MT_TRACKING_ID, value 284
                #   Event: ABS_MT_TRACKING_ID, value -1
                #   Event: BTN_LEFT, value 1
                #   Event: BTN_LEFT, value 0
                # In this case, the BTN_LEFT occurs when there is no finger.
                '1f_click_incorrect_behind_tid.dat': (1, (0, 1)),

                # A correct case with 1 finger: the event sequence comprises
                #   Event: ABS_MT_TRACKING_ID, value 284
                #   Event: BTN_LEFT, value 1
                #   Event: ABS_MT_TRACKING_ID, value -1
                #   Event: BTN_LEFT, value 0
                # In this case, the BTN_LEFT occurs when there is no finger.
                '1f_click.dat': (1, (1, 1)),

                # An incorrect case with 2 fingers: the event sequence comprises
                #   Event: ABS_MT_TRACKING_ID, value 18
                #   Event: BTN_LEFT, value 1
                #   Event: BTN_LEFT, value 0
                #   Event: ABS_MT_TRACKING_ID, value 19
                #   Event: ABS_MT_TRACKING_ID, value -1
                #   Event: ABS_MT_TRACKING_ID, value -1
                # In this case, the BTN_LEFT occurs when there is only 1 finger.
                '2f_clicks_incorrect_before_2nd_tid.dat': (2, (0, 1)),

                # An incorrect case with 2 fingers: the event sequence comprises
                #   Event: ABS_MT_TRACKING_ID, value 18
                #   Event: ABS_MT_TRACKING_ID, value 19
                #   Event: ABS_MT_TRACKING_ID, value -1
                #   Event: ABS_MT_TRACKING_ID, value -1
                #   Event: BTN_LEFT, value 1
                #   Event: BTN_LEFT, value 0
                # In this case, the BTN_LEFT occurs when there is only 1 finger.
                '2f_clicks_incorrect_behind_2_tids.dat': (2, (0, 1)),

                # A correct case with 2 fingers: the event sequence comprises
                #   Event: ABS_MT_TRACKING_ID, value 18
                #   Event: ABS_MT_TRACKING_ID, value 19
                #   Event: BTN_LEFT, value 1
                #   Event: ABS_MT_TRACKING_ID, value -1
                #   Event: ABS_MT_TRACKING_ID, value -1
                #   Event: BTN_LEFT, value 0
                # In this case, the BTN_LEFT occurs when there is only 1 finger.
                '2f_clicks.dat': (2, (1, 1)),
        }
        for filename, (fingers, expected_value) in files.items():
            packets = parse_tests_data(filename)
            validator = PhysicalClickValidator(self.criteria, fingers=fingers,
                                               device=dontcare)
            vlog = validator.check(packets)
            metric_name = self.mnprops.CLICK_CHECK_TIDS.format(fingers)
            for metric in vlog.metrics:
                if metric.name == metric_name:
                    self.assertEqual(metric.value, expected_value)


class RangeValidatorTest(BaseValidatorTest):
    """Unit tests for RangeValidator class."""

    def setUp(self):
        super(RangeValidatorTest, self).setUp()
        self.device = lumpy

    def _test_range(self, filename, expected_short_of_range_px):
        filepath = os.path.join(unittest_path_lumpy, filename)
        packets = parse_tests_data(filepath)
        validator = RangeValidator(conf.range_criteria, device=self.device)

        # Extract the gesture variation from the filename
        variation = (filename.split('/')[-1].split('.')[1],)

        # Determine the axis based on the direction in the gesture variation
        axis = (self.device.axis_x if validator.is_horizontal(variation)
                else self.device.axis_y if validator.is_vertical(variation)
                else None)
        self.assertTrue(axis is not None)

        # Convert from pixels to mms.
        expected_short_of_range_mm = self.device.pixel_to_mm_single_axis(
                expected_short_of_range_px, axis)

        vlog = validator.check(packets, variation)

        # There is only one metric in the metrics list.
        self.assertEqual(len(vlog.metrics), 1)
        actual_short_of_range_mm = vlog.metrics[0].value
        self.assertEqual(actual_short_of_range_mm, expected_short_of_range_mm)

    def test_range(self):
        """All physical click files specified below should fail."""
        # files_px is a dictionary of {filename: short_of_range_px}
        files_px = {
            '20130506_030025-fw_11.27-robot_sim/'
            'one_finger_to_edge.center_to_left.slow-lumpy-fw_11.27-'
                'robot_sim-20130506_031554.dat': 0,

            '20130506_030025-fw_11.27-robot_sim/'
            'one_finger_to_edge.center_to_left.slow-lumpy-fw_11.27-'
                'robot_sim-20130506_031608.dat': 0,

            '20130506_032458-fw_11.23-robot_sim/'
            'one_finger_to_edge.center_to_left.slow-lumpy-fw_11.23-'
                'robot_sim-20130506_032538.dat': 1,

            '20130506_032458-fw_11.23-robot_sim/'
            'one_finger_to_edge.center_to_left.slow-lumpy-fw_11.23-'
                'robot_sim-20130506_032549.dat': 1,
        }

        for filename, short_of_range_px in files_px.items():
            self._test_range(filename, short_of_range_px)


class StationaryFingerValidatorTest(BaseValidatorTest):
    """Unit tests for LinearityValidator class."""

    def setUp(self):
        super(StationaryFingerValidatorTest, self).setUp(show_spec_v2_flag=True)
        self.criteria = conf.stationary_finger_criteria()

    def _test_stationary_finger(self, filename, criteria, device):
        packets = parse_tests_data(filename)
        validator = StationaryFingerValidator(criteria, device=device)
        vlog = validator.check(packets)
        return vlog.score

    def test_stationary_finger_shift(self):
        """Test that the stationary shift due to 2nd finger tapping.

        Issue 7442: Cyapa : Second finger tap events influence stationary finger
        position
        """
        filename = 'stationary_finger_shift_with_2nd_finger_tap.dat'
        score = self._test_stationary_finger(filename, self.criteria, lumpy)
        self.assertTrue(score <= 0.1)

    def test_stationary_strongly_affected_by_2nd_moving_finger(self):
        """Test stationary finger strongly affected by 2nd moving finger with
        gaps.

        Issue 5812: [Cypress] reported positions of stationary finger strongly
        affected by nearby moving finger
        """
        filename = ('stationary_finger_strongly_affected_by_2nd_moving_finger_'
                    'with_gaps.dat')
        score = self._test_stationary_finger(filename, self.criteria, lumpy)
        self.assertTrue(score <= 0.1)


class NoLevelJumpValidatorTest(BaseValidatorTest):
    """Unit tests for NoLevelJumpValidator class."""

    def setUp(self):
        super(NoLevelJumpValidatorTest, self).setUp()
        self.criteria = conf.no_level_jump_criteria
        self.gesture_dir = 'drag_edge_thumb'

    def _get_score(self, filename, device):
        validator = NoLevelJumpValidator(self.criteria, device=device,
                                         slots=[0,])
        packets = parse_tests_data(filename, gesture_dir=self.gesture_dir)
        vlog = validator.check(packets)
        score = vlog.score
        return score

    def test_level_jumps(self):
        """Test files with level jumps."""
        filenames = [
            'drag_edge_thumb.horizontal.dat',
            'drag_edge_thumb.horizontal_2.dat',
            'drag_edge_thumb.horizontal_3.no_points.dat',
            'drag_edge_thumb.vertical.dat',
            'drag_edge_thumb.vertical_2.dat',
            'drag_edge_thumb.diagonal.dat',
        ]
        for filename in filenames:
            self.assertTrue(self._get_score(filename, lumpy) <= 0.6)

    def test_no_level_jumps(self):
        """Test files without level jumps."""
        filenames = [
            'drag_edge_thumb.horizontal.curvy.dat',
            'drag_edge_thumb.horizontal_2.curvy.dat',
            'drag_edge_thumb.vertical.curvy.dat',
            'drag_edge_thumb.vertical_2.curvy.dat',
        ]
        for filename in filenames:
            self.assertTrue(self._get_score(filename, lumpy) == 1.0)


class ReportRateValidatorTest(BaseValidatorTest):
    """Unit tests for ReportRateValidator class."""
    def setUp(self):
        super(ReportRateValidatorTest, self).setUp()
        self.criteria = '>= 60'

    def _get_score(self, filename, device):
        validator = ReportRateValidator(self.criteria, device=device)
        packets = parse_tests_data(filename)
        vlog = validator.check(packets)
        score = vlog.score
        return score

    def test_report_rate_scores(self):
        """Test the score of the report rate."""
        filename = '2f_scroll_diagonal.dat'
        self.assertTrue(self._get_score(filename, device=lumpy) <= 0.5)

        filename = 'one_finger_with_slot_0.dat'
        self.assertTrue(self._get_score(filename, device=lumpy) >= 0.9)

        filename = 'two_close_fingers_merging_changed_ids_gaps.dat'
        self.assertTrue(self._get_score(filename, device=lumpy) <= 0.5)

    def test_report_rate_without_slot(self):
        """Test report rate without specifying any slot."""
        filename_report_rate_pair = [
            ('2f_scroll_diagonal.dat', 40.31),
            ('one_finger_with_slot_0.dat', 148.65),
            ('two_close_fingers_merging_changed_ids_gaps.dat', 53.12),
        ]
        for filename, expected_report_rate in filename_report_rate_pair:
            validator = ReportRateValidator(self.criteria, device=dontcare)
            validator.check(parse_tests_data(filename))
            actual_report_rate = round(validator.report_rate, 2)
            self.assertAlmostEqual(actual_report_rate, expected_report_rate)

    def test_report_rate_with_slot(self):
        """Test report rate with slot=1"""
        # Compute actual_report_rate
        filename = ('stationary_finger_strongly_affected_by_2nd_moving_finger_'
                    'with_gaps.dat')
        validator = ReportRateValidator(self.criteria, device=dontcare,
                                        finger=1)
        validator.check(parse_tests_data(filename))
        actual_report_rate = validator.report_rate
        # Compute expected_report_rate
        first_syn_time = 2597.682925
        last_syn_time = 2604.534425
        num_packets = 591 - 1
        expected_report_rate = num_packets / (last_syn_time - first_syn_time)
        self.assertAlmostEqual(actual_report_rate, expected_report_rate)

    def _test_report_rate_metrics(self, filename, expected_values):
        packets = parse_tests_data(filename)
        validator = ReportRateValidator(self.criteria, device=lumpy)
        vlog = validator.check(packets)

        # Verify that there are 3 metrics
        number_metrics = 3
        self.assertEqual(len(vlog.metrics), number_metrics)

        # Verify the values of the 3 metrics.
        for i in range(number_metrics):
            self.assertAlmostEqual(vlog.metrics[i].value, expected_values[i])

    def test_report_rate_metrics(self):
        """Test the metrics of the report rates."""
        # files is a dictionary of
        #       {filename: ((# long_intervals, # all intervals),
        #                    ave_interval, max_interval)}
        files = {
            '2f_scroll_diagonal.dat':
                ((33, 33), 24.8057272727954, 26.26600000075996),
            'one_finger_with_slot_0.dat':
                ((1, 12), 6.727166666678386, 20.411999998032115),
            'two_close_fingers_merging_changed_ids_gaps.dat':
                ((13, 58), 18.82680942272318, 40.936946868896484),
        }

        for filename, values in files.items():
            self._test_report_rate_metrics(filename, values)


if __name__ == '__main__':
  unittest.main()
