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
(4) add a new gesture if necessary.

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

    def print_msg(self, msg):
        """Collect the messages to be printed within this module."""
        prefix_space = ' ' * 8
        formatted_msg = '%s%s' % (prefix_space, msg)
        self.msg_list.append(formatted_msg)


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
            if variation == VERTICAL:
                results.append(self._simple_linear_regression(list_y, list_x))
            else:
                results.append(self._simple_linear_regression(list_x, list_y))

        ave_distance = eval(self.aggregator)(results)
        length = (self.device_width if variation == VERTICAL
                                    else self.device_height)
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

        if variation == HORIZONTAL:
            diff_x = diff[0:2]
            ave_deviation = 1.0 * sum(diff_x) / len(diff_x) / spec_width
            actual_range_axis = actual_range[0:2]
            spec_range_axis = spec[0:2]
        elif variation == VERTICAL:
            diff_y = diff[2:4]
            ave_deviation = 1.0 * sum(diff_y) / len(diff_y) / spec_height
            actual_range_axis = actual_range[2:4]
            spec_range_axis = spec[2:4]
        else:
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
