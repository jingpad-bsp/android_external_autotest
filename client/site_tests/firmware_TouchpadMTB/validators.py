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
        name = self.__class__.__name__
        super(X..Validator, self).__init__(criteria_str, mf, name)
        self.fingers = fingers

    def check(self, packets, variation=None):
        """Check ..."""
        self.init_check(packets)
        xxx = self.packets.xxx()
        self.print_msg(...)
        return (self.fc.mf.grade(...), self.msg_list)


Note that it is also possible to instantiate a validator as
          XxxValidator('<= 0.05, ~ +0.05', slot=0)

    Difference between fingers and slot:
      . When specifying 'fingers', e.g., fingers=2, the purpose is to pass
        the information about how many fingers there are in the gesture. In
        this case, the events in a specific slot is usually not important.
        An example is to check how many fingers there are when making a click:
            PhysicalClickValidator('== 0', fingers=2)
      . When specifying 'slot', e.g., slot=0, the purpose is pass the slot
        number to the validator to examine detailed events in that slot.
        An example of such usage:
            LinearityValidator('<= 0.03, ~ +0.07', slot=0)
'''


import numpy as n
import os
import sys

import firmware_log
import firmware_utils
import fuzzy
import mtb

from touch_device import TouchpadDevice

# Include some constants
execfile('firmware_constants.py', globals())


def validate(packets, gesture, variation):
    """Validate a single gesture."""
    if packets is None:
        return (None, None)

    msg_list = []
    score_list = []
    logs = []
    for validator in gesture.validators:
        log = validator.check(packets, variation)
        if log is None:
            continue
        logs.append(log)
        score = log.get_score()

        if score is not None:
            score_list.append(score)
            # save the validator messages
            msg_validator_name = '%s' % log.get_name()
            msg_criteria = '    criteria_str: %s' % log.get_criteria()
            msg_score = 'score: %f' % score
            msg_list.append(os.linesep)
            msg_list.append(msg_validator_name)
            msg_list += log.get_details()
            msg_list.append(msg_criteria)
            msg_list.append(msg_score)

    return (score_list, msg_list, logs)


class BaseValidator(object):
    """Base class of validators."""
    aggregator = 'fuzzy.average'
    _device = None

    def __init__(self, criteria_str, mf=None, device=None, name=None):
        self.criteria_str = criteria_str
        self.fc = fuzzy.FuzzyCriteria(criteria_str, mf=mf)
        self.device = self._create_device() if device is None else device
        self.device_width, self.device_height = self.device.get_dimensions()
        self.packets = None
        self.msg_list = []
        self.log = firmware_log.ValidatorLog()
        self.log.insert_name(name)
        self.log.insert_criteria(criteria_str)

    def _create_device(self):
        """Create a touchpad device and reuse it."""
        if BaseValidator._device is None:
            BaseValidator._device = TouchpadDevice()
        return BaseValidator._device

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

    def log_name(self, msg):
        """Collect the validator name."""
        self.log.insert_name(msg)

    def log_details(self, msg):
        """Collect the detailed messages to be printed within this module."""
        prefix_space = ' ' * 4
        formatted_msg = '%s%s' % (prefix_space, msg)
        self.msg_list.append(formatted_msg)
        self.log.insert_details(formatted_msg)

    def log_score(self, score):
        """Collect the score."""
        self.log.insert_score(score)

    def log_error(self, msg):
        """Collect the error message."""
        self.log.insert_error(msg)


class LinearityValidator(BaseValidator):
    """Validator to verify linearity.

    Example:
        To check the linearity of the line drawn in slot 1:
          LinearityValidator('<= 0.03, ~ +0.07', slot=1)
    """
    # Define the partial group size for calculating Mean Squared Error
    MSE_PARTIAL_GROUP_SIZE = 1

    def __init__(self, criteria_str, mf=None, device=None, slot=0):
        name = self.__class__.__name__
        super(LinearityValidator, self).__init__(criteria_str, mf, device, name)
        self.slot = slot

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
        partial = min(asize, max(1, self.MSE_PARTIAL_GROUP_SIZE))
        spmse = n.square(ay - alpha - beta * ax)
        spmse.sort()
        spmse = spmse[asize - partial : asize]
        spmse = n.sqrt(n.average(spmse))

        return spmse

    def check(self, packets, variation=None):
        """Check if the packets conforms to specified criteria."""
        self.init_check(packets)
        resolution_x, resolution_y = self.device.get_resolutions()
        (list_x, list_y) = self.packets.get_x_y(self.slot)
        # Compuate average distance (fitting error) in pixels, and
        # average deviation on touchpad in mm.
        if self.is_vertical(variation):
            ave_distance = self._simple_linear_regression(list_y, list_x)
            deviation_touch = ave_distance / resolution_x
        else:
            ave_distance = self._simple_linear_regression(list_x, list_y)
            deviation_touch = ave_distance / resolution_y

        self.log_details('ave fitting error: %.2f' % ave_distance)
        msg_device = 'deviation (pad) slot[%d]: %.2f mm'
        self.log_details(msg_device % (self.slot, deviation_touch))
        self.log_score(self.fc.mf.grade(deviation_touch))
        return self.log


class RangeValidator(BaseValidator):
    """Validator to check the observed (x, y) positions should be within
    the range of reported min/max values.

    Example:
        To check the range of observed edge-to-edge positions:
          RangeValidator('<= 0.05, ~ +0.05')
    """

    def __init__(self, criteria_str, mf=None, device=None):
        name = self.__class__.__name__
        super(RangeValidator, self).__init__(criteria_str, mf, device, name)

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
            return None
        else:
            error_msg = 'A direction variation is missing in this gesture.'
            self.insert_error(error_msg)
            return None

        self.log_details('actual: %s' % str(actual_range_axis))
        self.log_details('spec: %s' % str(spec_range_axis))
        self.log_details('ave_deviation: %f' % ave_deviation)
        self.log_score(self.fc.mf.grade(ave_deviation))
        return self.log


class CountTrackingIDValidator(BaseValidator):
    """Validator to check the count of tracking IDs.

    Example:
        To verify if there is exactly one finger observed:
          CountTrackingIDValidator('== 1')
    """

    def __init__(self, criteria_str, mf=None, device=None):
        name = self.__class__.__name__
        super(CountTrackingIDValidator, self).__init__(criteria_str, mf,
                                                       device, name)

    def check(self, packets, variation=None):
        """Check the number of tracking IDs observed."""
        self.init_check(packets)
        # Get the count of tracking id
        count_tid = self.packets.get_number_contacts()
        self.log_details('count of trackid IDs: %d' % count_tid)
        self.log_score(self.fc.mf.grade(count_tid))
        return self.log


class StationaryFingerValidator(BaseValidator):
    """Validator to check the count of tracking IDs.

    Example:
        To verify if the stationary finger specified by the slot does not
        move larger than a specified radius:
          StationaryFingerValidator('<= 15 ~ +10')
    """

    def __init__(self, criteria_str, mf=None, device=None, slot=0):
        name = self.__class__.__name__
        super(StationaryFingerValidator, self).__init__(criteria_str, mf,
                                                        device, name)
        self.slot = slot

    def check(self, packets, variation=None):
        """Check the moving distance of the specified finger."""
        self.init_check(packets)
        # Get the count of tracking id
        distance = self.packets.get_largest_distance(self.slot)
        self.log_details('Largest distance in slot[%d]: %d' % (self.slot,
                                                               distance))
        self.log_score(self.fc.mf.grade(distance))
        return self.log


class NoGapValidator(BaseValidator):
    """Validator to make sure that there are no significant gaps in a line.

    Example:
        To verify if there is exactly one finger observed:
          NoGapValidator('<= 5, ~ +5', slot=1)
    """

    def __init__(self, criteria_str, mf=None, device=None, slot=0):
        name = self.__class__.__name__
        super(NoGapValidator, self).__init__(criteria_str, mf, device, name)
        self.slot = slot

    def check(self, packets, variation=None):
        """There should be no significant gaps in a line."""
        self.init_check(packets)
        # Get the largest gap ratio
        gap_ratio = self.packets.get_largest_gap_ratio(self.slot)
        msg = 'Largest gap ratio in slot[%d]: %f'
        self.log_details(msg % (self.slot, gap_ratio))
        self.log_score(self.fc.mf.grade(gap_ratio))
        return self.log


class NoReversedMotionValidator(BaseValidator):
    """Validator to measure the reversed motions in specified slots.

    Example:
        To measure the reversed motions in slot 0:
          NoReversedMotionValidator('== 0, ~ +20', slots=0)
    """

    def __init__(self, criteria_str, mf=None, device=None, slots=(0,)):
        name = self.__class__.__name__
        super(NoReversedMotionValidator, self).__init__(criteria_str, mf,
                                                        device, name)
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
            self.log_details(msg % (slot, reversed_motions))
            sum_reversed_motions += sum(map(abs, reversed_motions.values()))
        self.log_score(self.fc.mf.grade(sum_reversed_motions))
        return self.log


class CountPacketsValidator(BaseValidator):
    """Validator to check the number of packets.

    Example:
        To verify if there are enough packets received about the first finger:
          CountPacketsValidator('>= 3, ~ -3', slot=0)
    """

    def __init__(self, criteria_str, mf=None, device=None, slot=0):
        name = self.__class__.__name__
        super(CountPacketsValidator, self).__init__(criteria_str, mf, device,
                                                    name)
        self.slot = slot

    def check(self, packets, variation=None):
        """Check the number of packets in the specified slot."""
        self.init_check(packets)
        # Get the number of packets in that slot
        num_packets = self.packets.get_num_packets(self.slot)
        msg = 'Number of packets in slot[%d]: %s'
        self.log_details(msg % (self.slot, num_packets))
        self.log_score(self.fc.mf.grade(num_packets))
        return self.log


class PinchValidator(BaseValidator):
    """Validator to check the pinch to zoom in/out.

    Example:
        To verify that the two fingers are drawing closer:
          PinchValidator('>= 200, ~ -100')
    """

    def __init__(self, criteria_str, mf=None, device=None):
        name = self.__class__.__name__
        super(PinchValidator, self).__init__(criteria_str, mf, device, name)

    def check(self, packets, variation):
        """Check the number of packets in the specified slot."""
        self.init_check(packets)
        # Get the relative motion of the two fingers
        slots = (0, 1)
        relative_motion = self.packets.get_relative_motion(slots)
        if variation == ZOOM_OUT:
            relative_motion = -relative_motion
        msg = 'Relative motions of the two fingers: %.2f'
        self.log_details(msg % relative_motion)
        self.log_score(self.fc.mf.grade(relative_motion))
        return self.log


class PhysicalClickValidator(BaseValidator):
    """Validator to check the events generated by physical clicks

    Example:
        To verify the events generated by a one-finger physical click
          PhysicalClickValidator('== 1', fingers=1)
    """

    def __init__(self, criteria_str, fingers, mf=None, device=None):
        name = self.__class__.__name__
        super(PhysicalClickValidator, self).__init__(criteria_str, mf, device,
                                                     name)
        self.fingers = fingers

    def check(self, packets, variation=None):
        """Check the number of packets in the specified slot."""
        self.init_check(packets)
        # Get the number of packets in that slot
        count = self.packets.get_physical_clicks(self.fingers)
        msg = 'Count of %d-finger physical clicks: %s'
        self.log_details(msg % (self.fingers, count))
        self.log_score(self.fc.mf.grade(count))
        return self.log


class DrumrollValidator(BaseValidator):
    """Validator to check the drumroll problem.

    Example:
        To verify the events generated by a one-finger physical click
          DrumrollValidator('<= 20 ~ +30')
    """

    def __init__(self, criteria_str, mf=None, device=None):
        name = self.__class__.__name__
        super(DrumrollValidator, self).__init__(criteria_str, mf, device, name)

    def check(self, packets, variation=None):
        """The moving distance of the points in any tracking ID should be
        within the specified value.
        """
        self.init_check(packets)
        # Get the max distance of all tracking IDs
        max_distance = self.packets.get_max_distance_of_all_tracking_ids()
        msg = 'Max distance: %.2f'
        self.log_details(msg % max_distance)
        self.log_score(self.fc.mf.grade(max_distance))
        return self.log
