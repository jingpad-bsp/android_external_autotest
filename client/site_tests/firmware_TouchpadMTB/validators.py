# Copyright (c) 2012 The Chromium OS Authors. All rights reserved.
# Use of this source code is governed by a BSD-style license that can be
# found in the LICENSE file.

"""Validators to verify if events conform to specified criteria."""


'''
How to add a new validator/gesture:
(1) Implement a new validator class inheriting BaseValidator,
(2) add proper method in mtb.MTB class,
(3) add the new validator in test_conf, and
        'from validators import the_new_validator'
    in alphabetical order, and
(4) add the validator in relevant gestures; add a new gesture if necessary.

The validator template is as follows:

class XxxValidator(BaseValidator):
    """Validator to check ...

    Example:
        To check ...
          XxxValidator('<= 0.05, ~ +0.05', fingers=2)
    """

    def __init__(self, criteria_str, mf=None, fingers=1):
        super(X..Validator, self).__init__(criteria_str, mf)
        self.fingers = fingers

    def check(self, packets, variation=None):
        """Check ..."""
        self.init_check(packets)
        xxx = self.packets.xxx()
        self.print_msg(...)
        return (self.fc.mf.grade(...), self.msg_list)
'''


import numpy as n
import sys

import fuzzy
import firmware_utils
import mtb
import touch_device

# Include some constants
execfile('firmware_constants.py', globals())


def validate(packets, gesture, variation):
    """Validate a single gesture."""
    if packets is None:
        return (None, None)

    msg_list = []
    score_list = []
    for validator in gesture.validators:
        (score, check_msg) = validator.check(packets, variation)
        if score is not None:
            score_list.append(score)

            # save the validator messages
            validator_name = validator.__class__.__name__
            msg_validator_name = '    %s' % validator_name
            msg_criteria = '        criteria_str: %s' % validator.criteria_str
            msg_list.append(' ')
            msg_list.append(msg_validator_name)
            msg_list += check_msg
            msg_list.append(msg_criteria)
            msg_score = '    score: %f' % score
            msg_list.append(msg_score)

    return (score_list, msg_list)


class BaseValidator(object):
    """Base class of validators."""
    aggregator = 'fuzzy.average'

    def __init__(self, criteria_str, mf=None):
        self.criteria_str = criteria_str
        self.fc = fuzzy.FuzzyCriteria(criteria_str, mf=mf)
        self.device = touch_device.TouchpadDevice()
        self.device_width, self.device_height = self.device.get_dimensions()
        self.packets = None
        self.msg_list = []

    def init_check(self, packets):
        """Initialization before check() is called."""
        self.packets = mtb.MTB(packets)
        self.msg_list = []

    def _is_direction_in_variation(self, variation, directions):
        """Is any element of directions list found in variation?"""
        for direction in directions:
            if direction in variation:
                return True
        return False

    def is_horizontal(self, variation):
        """Is the direction horizontal?"""
        return self._is_direction_in_variation(variation, HORIZONTAL_DIRECTIONS)

    def is_vertical(self, variation):
        """Is the direction vertical?"""
        return self._is_direction_in_variation(variation, VERTICAL_DIRECTIONS)

    def is_diagonal(self, variation):
        """Is the direction diagonal?"""
        return self._is_direction_in_variation(variation, DIAGONAL_DIRECTIONS)

    def get_direction(self, variation):
        """Get the direction."""
        # TODO(josephsih): raise an exception if a proper direction is not found
        if self.is_horizontal(variation):
            return HORIZONTAL
        elif self.is_vertical(variation):
            return VERTICAL
        elif self.is_diagonal(variation):
            return DIAGONAL

    def print_msg(self, msg):
        """Collect the messages to be printed within this module."""
        prefix_space = ' ' * 8
        formatted_msg = '%s%s' % (prefix_space, msg)
        self.msg_list.append(formatted_msg)

    def print_error(self, msg):
        """Print error message."""
        self.print_msg('Error: %s.' %msg)


class LinearityValidator(BaseValidator):
    """Validator to verify linearity.

    Example:
        To check the linearity of two finger horizontal scrolling:
          LinearityValidator('<= 0.03, ~ +0.07', fingers=2)
    """

    def __init__(self, criteria_str, mf=None, fingers=1):
        super(LinearityValidator, self).__init__(criteria_str, mf)
        self.fingers = fingers

    def _simple_linear_regression(self, ax, ay):
        """Calculate the simple linear regression and returns the
           sum of squared residuals.

           ax: array x
           ay: array y
           This method tries to find alpha and beta in the formula
                ay = alpha + beta . ax
           such that it has the least sum of squared residuals.

           Reference:
             Simple linear regression:
               http://en.wikipedia.org/wiki/Simple_linear_regression
             Average absolute deviation (or mean absolute deviation) :
               http://en.wikipedia.org/wiki/Average_absolute_deviation
        """
        # Convert the list to the array presentation
        ax = 1.0 * n.array(ax)
        ay = 1.0 * n.array(ay)

        # If there are less than 2 data points, it is not a line at all.
        asize = ax.size
        if asize <= 2:
            return 0

        Sx = ax.sum()
        Sy = ay.sum()
        Sxx = n.square(ax).sum()
        Sxy = n.dot(ax, ay)
        Syy = n.square(ay).sum()
        Sx2 = Sx * Sx
        Sy2 = Sy * Sy

        # compute Mean of x and y
        Mx = ax.mean()
        My = ay.mean()

        # Compute beta and alpha of the linear regression
        beta = 1.0 * (asize * Sxy - Sx * Sy) / (asize * Sxx - Sx2)
        alpha = My - beta * Mx

        # spmse: squared root of partial mean squared error
        partial = max(1, int(0.1 * asize))
        partial = min(asize, 10)
        spmse = n.square(ay - alpha - beta * ax)
        spmse.sort()
        spmse = spmse[asize - partial : asize]
        spmse = n.sqrt(n.average(spmse))

        return spmse

    def check(self, packets, variation=None):
        """Check if the packets conforms to specified criteria."""
        self.init_check(packets)
        results = []
        for slot in range(self.fingers):
            (list_x, list_y) = self.packets.get_x_y(slot)
            if self.is_vertical(variation):
                results.append(self._simple_linear_regression(list_y, list_x))
                length = self.device_width
            else:
                results.append(self._simple_linear_regression(list_x, list_y))
                length = self.device_height

        ave_distance = eval(self.aggregator)(results)
        ave_deviation = ave_distance / length
        self.print_msg('average distance: %f' % ave_distance)
        self.print_msg('ave_deviation: %f' % ave_deviation)
        return (self.fc.mf.grade(ave_deviation), self.msg_list)


class RangeValidator(BaseValidator):
    """Validator to check the observed (x, y) positions should be within
    the range of reported min/max values.

    Example:
        To check the range of observed edge-to-edge positions:
          RangeValidator('<= 0.05, ~ +0.05')
    """

    def check(self, packets, variation=None):
        """Check the left/right or top/bottom range based on the direction."""
        self.init_check(packets)
        actual_range = self.packets.get_range()
        spec = self.device.get_edges()
        spec_width = spec[1] - spec[0]
        spec_height = spec[3] - spec[2]
        diff = map(lambda a, b: abs(a - b), actual_range, spec)

        if self.is_horizontal(variation):
            diff_x = diff[0:2]
            ave_deviation = 1.0 * sum(diff_x) / len(diff_x) / spec_width
            actual_range_axis = actual_range[0:2]
            spec_range_axis = spec[0:2]
        elif self.is_vertical(variation):
            diff_y = diff[2:4]
            ave_deviation = 1.0 * sum(diff_y) / len(diff_y) / spec_height
            actual_range_axis = actual_range[2:4]
            spec_range_axis = spec[2:4]
        elif self.is_diagonal(variation):
            # No need to check range on diagonal lines since we have
            # checked range on horizontal/vertical lines.
            # It is also difficult to make two-finger tracking precisely from
            # the very corner to the other corner.
            return (None, self.msg_list)
        else:
            error_msg = 'A direction variation is missing in this gesture.'
            self.print_error(error_msg)
            return (None, self.msg_list)

        self.print_msg('actual: %s' % str(actual_range_axis))
        self.print_msg('spec: %s' % str(spec_range_axis))
        self.print_msg('ave_deviation: %f' % ave_deviation)
        return (self.fc.mf.grade(ave_deviation), self.msg_list)


class CountTrackingIDValidator(BaseValidator):
    """Validator to check the count of tracking IDs.

    Example:
        To verify if there is exactly one finger observed:
          CountTrackingIDValidator('== 1')
    """

    def __init__(self, criteria_str, mf=None):
        super(CountTrackingIDValidator, self).__init__(criteria_str, mf)

    def check(self, packets, variation=None):
        """Check the number of tracking IDs observed."""
        self.init_check(packets)
        # Get the count of tracking id
        count_tid = self.packets.get_number_contacts()
        self.print_msg('count of trackid IDs: %d' % count_tid)
        return (self.fc.mf.grade(count_tid), self.msg_list)


class StationaryFingerValidator(BaseValidator):
    """Validator to check the count of tracking IDs.

    Example:
        To verify if the stationary finger specified by the slot does not
        move larger than a specified radius:
          StationaryFingerValidator('<= 15 ~ +10')
    """

    def __init__(self, criteria_str, mf=None, slot=0):
        super(StationaryFingerValidator, self).__init__(criteria_str, mf)
        self.slot = slot

    def check(self, packets, variation=None):
        """Check the moving distance of the specified finger."""
        self.init_check(packets)
        # Get the count of tracking id
        distance = self.packets.get_largest_distance(self.slot)
        self.print_msg('Largest distance in slot[%d]: %d' % (self.slot,
                                                             distance))
        return (self.fc.mf.grade(distance), self.msg_list)


class NoGapValidator(BaseValidator):
    """Validator to make sure that there are no significant gaps in a line.

    Example:
        To verify if there is exactly one finger observed:
          NoGapValidator('<= 5, ~ +5', slot=1)
    """

    def __init__(self, criteria_str, mf=None, slot=0):
        super(NoGapValidator, self).__init__(criteria_str, mf)
        self.slot = slot

    def check(self, packets, variation=None):
        """There should be no significant gaps in a line."""
        self.init_check(packets)
        # Get the largest gap ratio
        gap_ratio = self.packets.get_largest_gap_ratio(self.slot)
        msg = 'Largest gap ratio in slot[%d]: %f'
        self.print_msg(msg % (self.slot, gap_ratio))
        return (self.fc.mf.grade(gap_ratio), self.msg_list)


class NoReversedMotionValidator(BaseValidator):
    """Validator to measure the reversed motions in specified slots.

    Example:
        To measure the reversed motions in slot 0:
          NoReversedMotionValidator('== 0, ~ +20', slots=0)
    """

    def __init__(self, criteria_str, mf=None, slots=(0,)):
        super(NoReversedMotionValidator, self).__init__(criteria_str, mf)
        self.slots = (slots,) if isinstance(slots, int) else slots

    def check(self, packets, variation=None):
        """There should be no reversed motions in a slot."""
        self.init_check(packets)
        sum_reversed_motions = 0
        direction = self.get_direction(variation)
        for slot in self.slots:
            # Get the reversed motions if any
            reversed_motions = self.packets.get_reversed_motions(slot,
                                                                 direction)
            msg = 'Reversed motions in slot[%d]: %s'
            self.print_msg(msg % (slot, reversed_motions))
            sum_reversed_motions += sum(map(abs, reversed_motions.values()))
        return (self.fc.mf.grade(sum_reversed_motions), self.msg_list)


class CountPacketsValidator(BaseValidator):
    """Validator to check the number of packets.

    Example:
        To verify if there are enough packets received about the first finger:
          CountPacketsValidator('>= 3, ~ -3', slot=0)
    """

    def __init__(self, criteria_str, mf=None, slot=0):
        super(CountPacketsValidator, self).__init__(criteria_str, mf)
        self.slot = slot

    def check(self, packets, variation=None):
        """Check the number of packets in the specified slot."""
        self.init_check(packets)
        # Get the number of packets in that slot
        num_packets = self.packets.get_num_packets(self.slot)
        msg = 'Number of packets in slot[%d]: %s'
        self.print_msg(msg % (self.slot, num_packets))
        return (self.fc.mf.grade(num_packets), self.msg_list)


class PinchValidator(BaseValidator):
    """Validator to check the pinch to zoom in/out.

    Example:
        To verify that the two fingers are drawing closer:
          PinchValidator('>= 200, ~ -100')
    """

    def __init__(self, criteria_str, mf=None):
        super(PinchValidator, self).__init__(criteria_str, mf)

    def check(self, packets, variation):
        """Check the number of packets in the specified slot."""
        self.init_check(packets)
        # Get the relative motion of the two fingers
        slots = (0, 1)
        relative_motion = self.packets.get_relative_motion(slots)
        if variation == ZOOM_OUT:
            relative_motion = -relative_motion
        msg = 'Relative motions of the two fingers: %.2f'
        self.print_msg(msg % relative_motion)
        return (self.fc.mf.grade(relative_motion), self.msg_list)


class PhysicalClickValidator(BaseValidator):
    """Validator to check the events generated by physical clicks

    Example:
        To verify the events generated by a one-finger physical click
          PhysicalClickValidator('== 1', fingers=1)
    """

    def __init__(self, criteria_str, fingers, mf=None):
        super(PhysicalClickValidator, self).__init__(criteria_str, mf)
        self.fingers = fingers

    def check(self, packets, variation=None):
        """Check the number of packets in the specified slot."""
        self.init_check(packets)
        # Get the number of packets in that slot
        count = self.packets.get_physical_clicks(self.fingers)
        msg = 'Count of %d-finger physical clicks: %s'
        self.print_msg(msg % (self.fingers, count))
        return (self.fc.mf.grade(count), self.msg_list)
