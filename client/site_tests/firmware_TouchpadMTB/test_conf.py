# -*- coding: utf-8 -*-
#
# Copyright (c) 2012 The Chromium OS Authors. All rights reserved.
# Use of this source code is governed by a BSD-style license that can be
# found in the LICENSE file.

"""This configuration file defines the gestures to perform."""

from firmware_utils import Gesture
from validators import (CountTrackingIDValidator,
                        LinearityValidator,
                        NoGapValidator,
                        RangeValidator,
                        StationaryFingerValidator,
)

# Include some constants
execfile('firmware_constants.py', globals())


# Define which score aggregator is to be used. A score aggregator collects
# the scores from every tests and calculates the final score for the touchpad
# firmware test suite.
score_aggregator = 'fuzzy.average'


# Define the gesture list that the user needs to perform in the test suite.
gesture_list = [
    Gesture(
        name='stationary_finger_not_affected_by_2nd_moving_finger',
        variations=(HORIZONTAL, VERTICAL, DIAGONAL),
        prompt='Place your left finger on the {0} side. '
               'And use 2nd finger to draw {1}.',
        subprompt={
            HORIZONTAL: ('lower half', 'a horizontal line from left to right'),
            VERTICAL: ('left hand', 'a vertical line from top to bottom'),
            DIAGONAL: ('near center', 'a right half circle'),
        },
        validators=(
            StationaryFingerValidator('<= 20, ~ +20', slot=0),
            NoGapValidator('<= 5, ~ +5', slot=1),
            CountTrackingIDValidator('== 2'),
        ),
    ),

    Gesture(
        name='one_finger_tracking',
        variations=(HORIZONTAL, VERTICAL, DIAGONAL),
        prompt='Draw a {0} line {1}.',
        subprompt={
            HORIZONTAL: ('horizontal', 'from left edge to right edge'),
            VERTICAL: ('vertical', 'from top edge to bottom edge'),
            DIAGONAL: ('diagonal',
                       'from lower left corner to upper right corner'),
        },
        validators=(
            CountTrackingIDValidator('== 1'),
            LinearityValidator('<= 0.03, ~ +0.07'),
            RangeValidator('<= 0.05, ~ +0.05'),
        ),
    ),

    Gesture(
        name='two_finger_tracking',
        variations=(HORIZONTAL, VERTICAL, DIAGONAL),
        prompt='Use two fingers to draw {0} lines {1}.',
        subprompt={
            HORIZONTAL: ('horizontal', 'from left edge to right edge'),
            VERTICAL: ('vertical', 'from top edge to bottom edge'),
            DIAGONAL: ('diagonal',
                       'from lower left corner to upper right corner'),
        },
        validators=(
            CountTrackingIDValidator('== 2'),
            LinearityValidator('<= 0.03, ~ +0.07', fingers=2),
        ),
    ),
]


class FileName:
    """A dummy class to hold the attributes in a test file name."""
    pass
filename = FileName()
filename.sep = '-'
filename.ext = 'dat'
