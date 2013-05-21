# Copyright (c) 2012 The Chromium OS Authors. All rights reserved.
# Use of this source code is governed by a BSD-style license that can be
# found in the LICENSE file.
#

"""This module contains unit tests for the classes in the validators module."""

import os.path
import unittest

import common_unittest_utils
import common_util
import test_conf as conf

from common_unittest_utils import MockTouchDevice, parse_tests_data
from firmware_constants import GV
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


class BaseValidatorTest(unittest.TestCase):
    """A base class for all ValidatorTest classes."""

    def setUp(self):
        """Set up mocked devices for various test boards."""
        # define supported platforms
        self.ALEX= 'alex'
        self.LUMPY = 'lumpy'
        self.LINK = 'link'
        self.supported_platforms = [self.ALEX, self.LUMPY, self.LINK]
        self.mock_device = {}
        description_path = common_unittest_utils.get_device_description_path()

        for platform in self.supported_platforms:
            description_filename = '%s.device' % platform
            description_filepath = os.path.join(description_path,
                                                description_filename)
            if not os.path.isfile(description_filepath):
                self.mock_device[platform] = None
                warn_msg = 'Warning: device description file %s does not exist'
                print msg % description_filepath
                continue
            query_cmd = 'cat %s' % description_filepath
            device_description = common_util.simple_system_output(query_cmd)
            self.mock_device[platform] = MockTouchDevice(device_description)


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
                                             self.mock_device[self.LUMPY])
        self.assertTrue(score == 0)

    def test_one_finger_fast_swipe_id_split(self):
        """One finger fast swipe resulting in IDs split.

        Issue: 7869: Lumpy: Tracking ID reassigned during quick-2F-swipe
        """
        filename = 'one_finger_fast_swipe_id_split.dat'
        score = self._test_count_tracking_id(filename, '== 1',
                                             self.mock_device[self.LUMPY])
        self.assertTrue(score == 0)

    def test_two_fingers_fast_flick_id_split(self):
        """Two figners fast flick resulting in IDs split.

        Issue: 7869: Lumpy: Tracking ID reassigned during quick-2F-swipe
        """
        filename = 'two_finger_fast_flick_id_split.dat'
        score = self._test_count_tracking_id(filename, '== 2',
                                             self.mock_device[self.LUMPY])
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

    def test_drumroll_lumpy(self):
        """Should catch the drumroll on lumpy.

        Issue 7809: Lumpy: Drumroll bug in firmware
        Max distance: 52.02 px
        """
        filename = 'drumroll_lumpy.dat'
        score = self._test_drumroll(filename, self.criteria,
                                    self.mock_device[self.LUMPY])
        self.assertTrue(score == 0)

    def test_drumroll_lumpy_1(self):
        """Should catch the drumroll on lumpy.

        Issue 7809: Lumpy: Drumroll bug in firmware
        Max distance: 43.57 px
        """
        filename = 'drumroll_lumpy_1.dat'
        score = self._test_drumroll(filename, self.criteria,
                                    self.mock_device[self.LUMPY])
        self.assertTrue(score <= 0.15)

    def test_no_drumroll_link(self):
        """Should pass (score == 1) when there is no drumroll.

        Issue 7809: Lumpy: Drumroll bug in firmware
        Max distance: 2.92 px
        """
        filename = 'no_drumroll_link.dat'
        score = self._test_drumroll(filename, self.criteria,
                                    self.mock_device[self.LINK])
        self.assertTrue(score == 1)


class LinearityValidatorTest(BaseValidatorTest):
    """Unit tests for LinearityValidator class."""

    def setUp(self):
        super(LinearityValidatorTest, self).setUp()
        self.criteria = conf.linearity_criteria

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
                                               self.mock_device[self.ALEX])
        self.assertTrue(scores[0] == 0)
        self.assertTrue(scores[1] == 0)

    def test_linearity_criteria1(self):
        """The validator gets score betwee 0 and 1."""
        criteria_str = '<= 0.01, ~ +3.0'
        scores = self._test_linearity_criteria(criteria_str, (0, 1),
                                               self.mock_device[self.ALEX])
        self.assertTrue(scores[0] > 0 and scores[0] < 1)
        self.assertTrue(scores[1] > 0 and scores[1] < 1)

    def test_linearity_criteria2(self):
        """The validator gets score of 1 due to very relaxed criteria."""
        criteria_str = '<= 10, ~ +10'
        scores = self._test_linearity_criteria(criteria_str, (0, 1),
                                               self.mock_device[self.ALEX])
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
                self.mock_device[self.LUMPY], GV.DIAGONAL)
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
                self.mock_device[self.LUMPY], GV.HORIZONTAL)
        self.assertTrue(scores[1] <= 0.1)

    def test_thumb_edge(self):
        """Test thumb edge wobble.

        Issue 7554: thumb edge behavior.
        """
        filename = 'thumb_edge_wobble.dat'
        scores = self._test_linearity_validator(filename, self.criteria, 0,
                self.mock_device[self.LUMPY], GV.HORIZONTAL)
        self.assertTrue(scores[0] < 0.5)

    def test_two_close_fingers_merging_changed_ids_gaps(self):
        """Test close finger merging - causes id changes

        Issue 7555: close finger merging - causes id changes.
        """
        filename = 'two_close_fingers_merging_changed_ids_gaps.dat'
        scores = self._test_linearity_validator(filename, self.criteria, 0,
                self.mock_device[self.LUMPY], GV.VERTICAL)
        self.assertTrue(scores[0] < 0.3)

    def test_jagged_two_finger_scroll(self):
        """Test jagged two finger scroll.

        Issue 7650: Cyapa : poor two fat fingers horizontal scroll performance -
        jagged lines
        """
        filename = 'jagged_two_finger_scroll_horizontal.dat'
        scores = self._test_linearity_validator(filename, self.criteria, (0, 1),
                self.mock_device[self.LUMPY], GV.HORIZONTAL)
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
                self.mock_device[self.LUMPY], GV.DIAGONAL)
        self.assertTrue(scores[0] < 0.3)

    def test_simple_linear_regression0(self):
        device = self.mock_device[self.LUMPY]
        validator = LinearityValidator('<= 0.2, ~ +0.3', device=device, slot=0)
        validator.init_check()
        # A perfect line from bottom left to top right
        list_x = [1, 2, 3, 4, 5, 6, 7, 8]
        list_y = [20, 40, 60, 80, 100, 120, 140, 160]
        spmse = validator._simple_linear_regression(list_x, list_y)
        self.assertEqual(spmse, 0)

    def test_simple_linear_regression1(self):
        device = self.mock_device[self.LUMPY]
        validator = LinearityValidator('<= 0.2, ~ +0.3', device=device, slot=0)
        validator.init_check()
        # Another perfect line from top left to bottom right
        list_x = [1, 2, 3, 4, 5, 6, 7, 8]
        list_y = [160, 140, 120, 100, 80, 60, 40, 20]
        spmse = validator._simple_linear_regression(list_x, list_y)
        self.assertEqual(spmse, 0)

    def test_simple_linear_regression2(self):
        device = self.mock_device[self.LUMPY]
        validator = LinearityValidator('<= 0.2, ~ +0.3', device=device, slot=0)
        validator.init_check()
        # An outlier in y axis
        list_x = [1, 2, 3, 4, 5, 6, 7, 8]
        list_y = [20, 40, 60, 70, 100, 120, 140, 160]
        spmse = validator._simple_linear_regression(list_x, list_y)
        self.assertTrue(spmse > 0)

    def test_simple_linear_regression3(self):
        device = self.mock_device[self.LUMPY]
        validator = LinearityValidator('<= 0.2, ~ +0.3', device=device, slot=0)
        validator.init_check()
        # Repeated values in x axis
        list_x = [1, 2, 2, 4, 5, 6, 7, 8]
        list_y = [20, 40, 60, 80, 100, 120, 140, 160]
        spmse = validator._simple_linear_regression(list_x, list_y)
        self.assertTrue(spmse > 0)


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
        mock_device = self.mock_device[self.LUMPY]
        score0 = self._test_no_gap(filename, self.criteria, mock_device, 0)
        score1 = self._test_no_gap(filename, self.criteria, mock_device, 1)
        self.assertTrue(score0 <= 0.1)
        self.assertTrue(score1 <= 0.1)

    def test_gap_new_finger_arriving_or_departing(self):
        """Test gap when new finger arriving or departing.

        Issue: 8005: Cyapa : gaps appear when new finger arrives or departs
        """
        filename = 'gap_new_finger_arriving_or_departing.dat'
        mock_device = self.mock_device[self.LUMPY]
        score = self._test_no_gap(filename, self.criteria, mock_device, 0)
        self.assertTrue(score <= 0.3)

    def test_one_stationary_finger_2nd_finger_moving_gaps(self):
        """Test one stationary finger resulting in 2nd finger moving gaps."""
        filename = 'one_stationary_finger_2nd_finger_moving_gaps.dat'
        mock_device = self.mock_device[self.LUMPY]
        score = self._test_no_gap(filename, self.criteria, mock_device, 1)
        self.assertTrue(score <= 0.1)

    def test_resting_finger_2nd_finger_moving_gaps(self):
        """Test resting finger resulting in 2nd finger moving gaps.

        Issue 7648: Cyapa : Resting finger plus one finger move generates a gap
        """
        filename = 'resting_finger_2nd_finger_moving_gaps.dat'
        mock_device = self.mock_device[self.LUMPY]
        score = self._test_no_gap(filename, self.criteria, mock_device, 1)
        self.assertTrue(score <= 0.3)


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
        device = self.mock_device[self.LUMPY]
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
        device = self.mock_device[self.LUMPY]
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
        device = self.mock_device[self.LUMPY]
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
        device = self.mock_device[self.LUMPY]
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
        lumpy = self.mock_device[self.LUMPY]

        filename = '2f_scroll_diagonal.dat'
        self.assertTrue(self._get_score(filename, device=lumpy) <= 0.5)

        filename = 'one_finger_with_slot_0.dat'
        self.assertTrue(self._get_score(filename, device=lumpy) >= 0.9)

        filename = 'two_close_fingers_merging_changed_ids_gaps.dat'
        self.assertTrue(self._get_score(filename, device=lumpy) <= 0.5)


if __name__ == '__main__':
  unittest.main()
