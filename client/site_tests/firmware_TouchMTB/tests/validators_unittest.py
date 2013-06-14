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

from common_unittest_utils import parse_tests_data
from firmware_constants import GV
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


# Define supported platforms
ALEX= 'alex'
LUMPY = 'lumpy'
LINK = 'link'
PLATFORMS = [ALEX, LUMPY, LINK]

unittest_path_lumpy = os.path.join(os.getcwd(), 'tests/logs/lumpy')


def create_mocked_devices():
    """Create mocked devices of specified platforms."""
    description_path = common_unittest_utils.get_device_description_path()
    mocked_device = {}
    for platform in PLATFORMS:
        description_filename = '%s.device' % platform
        description_filepath = os.path.join(description_path,
                                            description_filename)
        if not os.path.isfile(description_filepath):
            mocked_device[platform] = None
            warn_msg = 'Warning: device description file %s does not exist'
            print msg % description_filepath
            continue
        with open(description_filepath) as f:
            device_description = f.read()
        mocked_device[platform] = TouchDevice(
                device_description=device_description)
    return mocked_device


mocked_device = create_mocked_devices()


class BaseValidatorTest(unittest.TestCase):
    """A base class for all ValidatorTest classes."""

    def setUp(self):
        """Set up mocked devices for various test boards."""
        global mocked_device
        self.mocked_device = mocked_device


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
        score = self._test_count_tracking_id(filename, '== 2',
                                             self.mocked_device[LUMPY])
        self.assertTrue(score == 0)

    def test_one_finger_fast_swipe_id_split(self):
        """One finger fast swipe resulting in IDs split.

        Issue: 7869: Lumpy: Tracking ID reassigned during quick-2F-swipe
        """
        filename = 'one_finger_fast_swipe_id_split.dat'
        score = self._test_count_tracking_id(filename, '== 1',
                                             self.mocked_device[LUMPY])
        self.assertTrue(score == 0)

    def test_two_fingers_fast_flick_id_split(self):
        """Two figners fast flick resulting in IDs split.

        Issue: 7869: Lumpy: Tracking ID reassigned during quick-2F-swipe
        """
        filename = 'two_finger_fast_flick_id_split.dat'
        score = self._test_count_tracking_id(filename, '== 2',
                                             self.mocked_device[LUMPY])
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
        score = self._test_drumroll(filename, self.criteria,
                                    self.mocked_device[LUMPY])
        self.assertTrue(score == 0)

    def test_drumroll_lumpy_1(self):
        """Should catch the drumroll on lumpy.

        Issue 7809: Lumpy: Drumroll bug in firmware
        Max distance: 43.57 px
        """
        filename = 'drumroll_lumpy_1.dat'
        score = self._test_drumroll(filename, self.criteria,
                                    self.mocked_device[LUMPY])
        self.assertTrue(score <= 0.15)

    def test_no_drumroll_link(self):
        """Should pass (score == 1) when there is no drumroll.

        Issue 7809: Lumpy: Drumroll bug in firmware
        Max distance: 2.92 px
        """
        filename = 'no_drumroll_link.dat'
        score = self._test_drumroll(filename, self.criteria,
                                    self.mocked_device[LINK])
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
        device = self.mocked_device[LUMPY]
        for filename, expected_max_value in expected_max_values.items():
            metrics = self._get_drumroll_metrics(filename, criteria, device)
            actual_max_value = max([m.value for m in metrics])
            self.assertAlmostEqual(expected_max_value, actual_max_value)


class LinearityValidatorTest(BaseValidatorTest):
    """Unit tests for LinearityValidator class."""

    def setUp(self):
        super(LinearityValidatorTest, self).setUp()
        self.criteria = conf.linearity_criteria
        validators.show_new_spec = False

    def _test_linearity_criteria(self, criteria_str, slots, device):
        filename = '2f_scroll_diagonal.dat'
        direction = GV.DIAGONAL
        packets = parse_tests_data(filename)
        scores = {}
        for slot in slots:
            validator = LinearityValidator(criteria_str, device=device,
                                           slot=slot)
            scores[slot] = validator.check(packets, direction).score
        return scores

    def test_linearity_criteria0(self):
        """The scores are 0s due to strict criteria."""
        criteria_str = '<= 0.01, ~ +0.01'
        scores = self._test_linearity_criteria(criteria_str, (0, 1),
                                               self.mocked_device[ALEX])
        self.assertTrue(scores[0] == 0)
        self.assertTrue(scores[1] == 0)

    def test_linearity_criteria1(self):
        """The validator gets score betwee 0 and 1."""
        criteria_str = '<= 0.01, ~ +3.0'
        scores = self._test_linearity_criteria(criteria_str, (0, 1),
                                               self.mocked_device[ALEX])
        self.assertTrue(scores[0] > 0 and scores[0] < 1)
        self.assertTrue(scores[1] > 0 and scores[1] < 1)

    def test_linearity_criteria2(self):
        """The validator gets score of 1 due to very relaxed criteria."""
        criteria_str = '<= 10, ~ +10'
        scores = self._test_linearity_criteria(criteria_str, (0, 1),
                                               self.mocked_device[ALEX])
        self.assertTrue(scores[0] == 1)
        self.assertTrue(scores[1] == 1)

    def _test_linearity_validator(self, filename, criteria, slots, device,
                                  direction):
        packets = parse_tests_data(filename)
        scores = {}
        if isinstance(slots, int):
            slots = (slots,)
        for slot in slots:
            validator = LinearityValidator(criteria, device=device, slot=slot)
            scores[slot] = validator.check(packets, direction).score
        return scores

    def test_two_finger_jagged_lines(self):
        """Test two-finger jagged lines."""
        filename = 'two_finger_tracking.diagonal.slow.dat'
        scores = self._test_linearity_validator(filename, self.criteria, (0, 1),
                self.mocked_device[LUMPY], GV.DIAGONAL)
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
                self.mocked_device[LUMPY], GV.HORIZONTAL)
        self.assertTrue(scores[1] <= 0.1)

    def test_thumb_edge(self):
        """Test thumb edge wobble.

        Issue 7554: thumb edge behavior.
        """
        filename = 'thumb_edge_wobble.dat'
        scores = self._test_linearity_validator(filename, self.criteria, 0,
                self.mocked_device[LUMPY], GV.HORIZONTAL)
        self.assertTrue(scores[0] < 0.5)

    def test_two_close_fingers_merging_changed_ids_gaps(self):
        """Test close finger merging - causes id changes

        Issue 7555: close finger merging - causes id changes.
        """
        filename = 'two_close_fingers_merging_changed_ids_gaps.dat'
        scores = self._test_linearity_validator(filename, self.criteria, 0,
                self.mocked_device[LUMPY], GV.VERTICAL)
        self.assertTrue(scores[0] < 0.3)

    def test_jagged_two_finger_scroll(self):
        """Test jagged two finger scroll.

        Issue 7650: Cyapa : poor two fat fingers horizontal scroll performance -
        jagged lines
        """
        filename = 'jagged_two_finger_scroll_horizontal.dat'
        scores = self._test_linearity_validator(filename, self.criteria, (0, 1),
                self.mocked_device[LUMPY], GV.HORIZONTAL)
        self.assertTrue(scores[0] < 0.3)
        self.assertTrue(scores[1] < 0.3)

    def test_first_point_jump(self):
        """Test the first point jump

        At slot 0, the positions of (x, y) looks like
            x: 208, 241, 242, 245, 246, ...
            y: 551, 594, 595, 597, 598, ...
        Note that the the first y position is a jump.
        """
        filename = 'two_finger_tracking.bottom_left_to_top_right.slow.dat'
        scores = self._test_linearity_validator(filename, self.criteria, 0,
                self.mocked_device[LUMPY], GV.DIAGONAL)
        self.assertTrue(scores[0] < 0.3)

    def test_simple_linear_regression0(self):
        device = self.mocked_device[LUMPY]
        validator = LinearityValidator('<= 0.2, ~ +0.3', device=device, slot=0)
        validator.init_check()
        # A perfect line from bottom left to top right
        list_x = [1, 2, 3, 4, 5, 6, 7, 8]
        list_y = [20, 40, 60, 80, 100, 120, 140, 160]
        spmse = validator._simple_linear_regression(list_x, list_y)
        self.assertEqual(spmse, 0)

    def test_simple_linear_regression1(self):
        device = self.mocked_device[LUMPY]
        validator = LinearityValidator('<= 0.2, ~ +0.3', device=device, slot=0)
        validator.init_check()
        # Another perfect line from top left to bottom right
        list_x = [1, 2, 3, 4, 5, 6, 7, 8]
        list_y = [160, 140, 120, 100, 80, 60, 40, 20]
        spmse = validator._simple_linear_regression(list_x, list_y)
        self.assertEqual(spmse, 0)

    def test_simple_linear_regression2(self):
        device = self.mocked_device[LUMPY]
        validator = LinearityValidator('<= 0.2, ~ +0.3', device=device, slot=0)
        validator.init_check()
        # An outlier in y axis
        list_x = [1, 2, 3, 4, 5, 6, 7, 8]
        list_y = [20, 40, 60, 70, 100, 120, 140, 160]
        spmse = validator._simple_linear_regression(list_x, list_y)
        self.assertTrue(spmse > 0)

    def test_simple_linear_regression3(self):
        device = self.mocked_device[LUMPY]
        validator = LinearityValidator('<= 0.2, ~ +0.3', device=device, slot=0)
        validator.init_check()
        # Repeated values in x axis
        list_x = [1, 2, 2, 4, 5, 6, 7, 8]
        list_y = [20, 40, 60, 80, 100, 120, 140, 160]
        spmse = validator._simple_linear_regression(list_x, list_y)
        self.assertTrue(spmse > 0)


class LinearityValidator2Test(BaseValidatorTest):
    """Unit tests for LinearityValidator2 class."""

    def setUp(self):
        super(LinearityValidator2Test, self).setUp()
        validators.set_show_spec_v2(True)
        self.validator = LinearityValidator(conf.linearity_criteria,
                                            device=self.mocked_device[LUMPY],
                                            slot=0)
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

    def tearDown(self):
        """Reset the show_spec_v2 so that other unit tests for spec v1 could be
        conducted as uaual.
        """
        validators.set_show_spec_v2(False)


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
        mocked_device = self.mocked_device[LUMPY]
        score0 = self._test_no_gap(filename, self.criteria, mocked_device, 0)
        score1 = self._test_no_gap(filename, self.criteria, mocked_device, 1)
        self.assertTrue(score0 <= 0.1)
        self.assertTrue(score1 <= 0.1)

    def test_gap_new_finger_arriving_or_departing(self):
        """Test gap when new finger arriving or departing.

        Issue: 8005: Cyapa : gaps appear when new finger arrives or departs
        """
        filename = 'gap_new_finger_arriving_or_departing.dat'
        mocked_device = self.mocked_device[LUMPY]
        score = self._test_no_gap(filename, self.criteria, mocked_device, 0)
        self.assertTrue(score <= 0.3)

    def test_one_stationary_finger_2nd_finger_moving_gaps(self):
        """Test one stationary finger resulting in 2nd finger moving gaps."""
        filename = 'one_stationary_finger_2nd_finger_moving_gaps.dat'
        mocked_device = self.mocked_device[LUMPY]
        score = self._test_no_gap(filename, self.criteria, mocked_device, 1)
        self.assertTrue(score <= 0.1)

    def test_resting_finger_2nd_finger_moving_gaps(self):
        """Test resting finger resulting in 2nd finger moving gaps.

        Issue 7648: Cyapa : Resting finger plus one finger move generates a gap
        """
        filename = 'resting_finger_2nd_finger_moving_gaps.dat'
        mocked_device = self.mocked_device[LUMPY]
        score = self._test_no_gap(filename, self.criteria, mocked_device, 1)
        self.assertTrue(score <= 0.3)


class PhysicalClickValidatorTest(BaseValidatorTest):
    """Unit tests for PhysicalClickValidator class."""

    def setUp(self):
        super(PhysicalClickValidatorTest, self).setUp()
        self.device = self.mocked_device[LUMPY]
        self.criteria = '== 1'

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


class StationaryFingerValidatorTest(BaseValidatorTest):
    """Unit tests for LinearityValidator class."""

    def setUp(self):
        super(StationaryFingerValidatorTest, self).setUp()
        self.criteria = conf.stationary_finger_criteria

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
        device = self.mocked_device[LUMPY]
        score = self._test_stationary_finger(filename, self.criteria, device)
        self.assertTrue(score <= 0.1)

    def test_stationary_strongly_affected_by_2nd_moving_finger(self):
        """Test stationary finger strongly affected by 2nd moving finger with
        gaps.

        Issue 5812: [Cypress] reported positions of stationary finger strongly
        affected by nearby moving finger
        """
        filename = ('stationary_finger_strongly_affected_by_2nd_moving_finger_'
                    'with_gaps.dat')
        device = self.mocked_device[LUMPY]
        score = self._test_stationary_finger(filename, self.criteria, device)
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
        device = self.mocked_device[LUMPY]
        for filename in filenames:
            self.assertTrue(self._get_score(filename, device) <= 0.6)

    def test_no_level_jumps(self):
        """Test files without level jumps."""
        filenames = [
            'drag_edge_thumb.horizontal.curvy.dat',
            'drag_edge_thumb.horizontal_2.curvy.dat',
            'drag_edge_thumb.vertical.curvy.dat',
            'drag_edge_thumb.vertical_2.curvy.dat',
        ]
        device = self.mocked_device[LUMPY]
        for filename in filenames:
            self.assertTrue(self._get_score(filename, device) == 1.0)


class ReportRateValidatorTest(BaseValidatorTest):
    """Unit tests for ReportRateValidator class."""
    def setUp(self):
        super(ReportRateValidatorTest, self).setUp()
        self.criteria = conf.report_rate_criteria

    def _get_score(self, filename, device):
        validator = ReportRateValidator(self.criteria, device=device)
        packets = parse_tests_data(filename)
        vlog = validator.check(packets)
        score = vlog.score
        return score

    def test_level_jumps(self):
        """Test files with level jumps."""
        lumpy = self.mocked_device[LUMPY]

        filename = '2f_scroll_diagonal.dat'
        self.assertTrue(self._get_score(filename, device=lumpy) <= 0.5)

        filename = 'one_finger_with_slot_0.dat'
        self.assertTrue(self._get_score(filename, device=lumpy) >= 0.9)

        filename = 'two_close_fingers_merging_changed_ids_gaps.dat'
        self.assertTrue(self._get_score(filename, device=lumpy) <= 0.5)


if __name__ == '__main__':
  unittest.main()
