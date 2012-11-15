# -*- coding: utf-8 -*-
#
# Copyright (c) 2012 The Chromium OS Authors. All rights reserved.
# Use of this source code is governed by a BSD-style license that can be
# found in the LICENSE file.

"""This configuration file defines the gestures to perform."""

from firmware_constants import MF, GV, RC
from validators import (CountPacketsValidator,
                        CountTrackingIDValidator,
                        DrumrollValidator,
                        LinearityValidator,
                        NoGapValidator,
                        NoReversedMotionValidator,
                        PhysicalClickValidator,
                        PinchValidator,
                        RangeValidator,
                        StationaryFingerValidator,
)


# Define which score aggregator is to be used. A score aggregator collects
# the scores from every tests and calculates the final score for the touchpad
# firmware test suite.
score_aggregator = 'fuzzy.average'


# Define some common criteria
count_packets_criteria = '>= 3, ~ -3'
drumroll_criteria = '<= 20, ~ +30'
linearity_criteria = '<= 0.8, ~ +2.4'
no_gap_criteria = '<= 1.8, ~ +1.0'
no_reversed_motion_criteria = '== 0, ~ +20'
pinch_criteria = '>= 200, ~ -100'
range_criteria = '<= 0.05, ~ +0.05'
stationary_finger_criteria = '<= 20, ~ +20'


# Define filename and path for html report
docroot = '/tmp'
report_basename = 'touchpad_firmware_report'
html_ext = '.html'
ENVIRONMENT_REPORT_HTML_NAME = 'REPORT_HTML_NAME'


# Define parameters for GUI
score_colors = ((0.9, 'blue'), (0.8, 'orange'), (0.0, 'red'))
num_chars_per_row = 28


# Define the path to find the robot gestures library path
robot_lib_path = '/usr/local/lib*'
python_package = 'python2.6'
gestures_sub_path = 'site-packages/gestures'


# Define the gesture names
ONE_FINGER_TRACKING = 'one_finger_tracking'
TWO_FINGER_TRACKING = 'two_finger_tracking'
FINGER_CROSSING = 'finger_crossing'
ONE_FINGER_SWIPE = 'one_finger_swipe'
TWO_FINGER_SWIPE = 'two_finger_swipe'
PINCH_TO_ZOOM = 'pinch_to_zoom'
ONE_FINGER_TAP = 'one_finger_tap'
TWO_FINGER_TAP = 'two_finger_tap'
ONE_FINGER_PHYSICAL_CLICK = 'one_finger_physical_click'
TWO_FINGER_PHYSICAL_CLICK = 'two_fingers_physical_click'
THREE_FINGER_PHYSICAL_CLICK = 'three_fingers_physical_click'
FOUR_FINGER_PHYSICAL_CLICK = 'four_fingers_physical_click'
FIVE_FINGER_PHYSICAL_CLICK = 'five_fingers_physical_click'
STATIONARY_FINGER_NOT_AFFECTED_BY_2ND_FINGER_TAPS = \
        'stationary_finger_not_affected_by_2nd_finger_taps'
FAT_FINGER_MOVE_WITH_RESTING_FINGER = 'fat_finger_move_with_resting_finger'
DRAG_EDGE_THUMB = 'drag_edge_thumb'
TWO_CLOSE_FINGERS_TRACKING = 'two_close_fingers_tracking'
RESTING_FINGER_PLUS_2ND_FINGER_MOVE = 'resting_finger_plus_2nd_finger_move'
TWO_FAT_FINGERS_TRACKING = 'two_fat_fingers_tracking'
FIRST_FINGER_TRACKING_AND_SECOND_FINGER_TAPS = \
        'first_finger_tracking_and_second_finger_taps'
DRUMROLL = 'drumroll'


# Define the complete list
gesture_names_complete = [
    ONE_FINGER_TRACKING,
    TWO_FINGER_TRACKING,
    FINGER_CROSSING,
    ONE_FINGER_SWIPE,
    TWO_FINGER_SWIPE,
    PINCH_TO_ZOOM,
    ONE_FINGER_TAP,
    TWO_FINGER_TAP,
    ONE_FINGER_PHYSICAL_CLICK,
    TWO_FINGER_PHYSICAL_CLICK,
    THREE_FINGER_PHYSICAL_CLICK,
    FOUR_FINGER_PHYSICAL_CLICK,
    FIVE_FINGER_PHYSICAL_CLICK,
    STATIONARY_FINGER_NOT_AFFECTED_BY_2ND_FINGER_TAPS,
    FAT_FINGER_MOVE_WITH_RESTING_FINGER,
    DRAG_EDGE_THUMB,
    TWO_CLOSE_FINGERS_TRACKING,
    RESTING_FINGER_PLUS_2ND_FINGER_MOVE,
    TWO_FAT_FINGERS_TRACKING,
    FIRST_FINGER_TRACKING_AND_SECOND_FINGER_TAPS,
    DRUMROLL,
]


# Define the list of one-finger and two-finger gestures to test using the robot.
gesture_names_robot = [
    ONE_FINGER_TRACKING,
    ONE_FINGER_SWIPE,
    ONE_FINGER_TAP,
    ONE_FINGER_PHYSICAL_CLICK,
    TWO_FINGER_TRACKING,
    TWO_FINGER_SWIPE,
    TWO_FINGER_TAP,
    TWO_FINGER_PHYSICAL_CLICK,
]


# Define the gestures to test using the robot with finger interaction.
gesture_names_robot_interaction = gesture_names_robot + [
    FINGER_CROSSING,
    STATIONARY_FINGER_NOT_AFFECTED_BY_2ND_FINGER_TAPS,
    RESTING_FINGER_PLUS_2ND_FINGER_MOVE,
]


# Define those gestures that the robot needs to pause so the user
# could adjust the robot or do finger interaction.
msg_step1 = 'Step 1: Place a metal finger on the %s of the touchpad now.'
msg_step2 = 'Step 2: Press SPACE when ready.'
msg_step3 = 'Step 3: Remember to lift the metal finger when robot has finished!'
gesture_names_robot_pause = {
    TWO_FINGER_TRACKING: {
        RC.PAUSE_TYPE: RC.PER_GESTURE,
        RC.PROMPT: (
            'Gesture: %s' % TWO_FINGER_TRACKING,
            'Step 1: Install two fingers for the robot now.',
            msg_step2,
            '',
        )
    },

    FINGER_CROSSING: {
        RC.PAUSE_TYPE: RC.PER_VARIATION,
        RC.PROMPT: (
            'Gesture: %s' % FINGER_CROSSING,
            msg_step1 % 'center',
            msg_step2,
            msg_step3,
        )
    },

    STATIONARY_FINGER_NOT_AFFECTED_BY_2ND_FINGER_TAPS: {
        RC.PAUSE_TYPE: RC.PER_VARIATION,
        RC.PROMPT: (
            'Gesture: %s' % STATIONARY_FINGER_NOT_AFFECTED_BY_2ND_FINGER_TAPS,
            msg_step1 % 'center',
            msg_step2,
            msg_step3,
        )
    },

    RESTING_FINGER_PLUS_2ND_FINGER_MOVE: {
        RC.PAUSE_TYPE: RC.PER_VARIATION,
        RC.PROMPT: (
            'Gesture: %s' % RESTING_FINGER_PLUS_2ND_FINGER_MOVE,
            msg_step1 % 'bottom left corner',
            msg_step2,
            msg_step3,
        )
    },
}


# Define the gesture list that the user needs to perform in the test suite.
def get_gesture_dict():
    gesture_dict = {
        ONE_FINGER_TRACKING:
        Gesture(
            name=ONE_FINGER_TRACKING,
            variations=((GV.LR, GV.RL, GV.TB, GV.BT, GV.BLTR, GV.TRBL),
                        (GV.SLOW, GV.NORMAL),
            ),
            prompt='Draw a {0} line {1} using a ruler in {2}.',
            subprompt={
                GV.LR: ('horizontal', 'from left edge to right edge',),
                GV.RL: ('horizontal', 'from right edge to left edge',),
                GV.TB: ('vertical', 'from top edge to bottom edge',),
                GV.BT: ('vertical', 'from bottom edge to top edge',),
                GV.BLTR: ('diagonal', 'from bottom left to top right',),
                GV.TRBL: ('diagonal', 'from top right to bottom left',),
                GV.SLOW: ('3 seconds',),
                GV.NORMAL: ('1 second',),
            },
            validators=(
                CountTrackingIDValidator('== 1'),
                LinearityValidator(linearity_criteria, slot=0),
                NoGapValidator(no_gap_criteria, slot=0),
                NoReversedMotionValidator(no_reversed_motion_criteria, slots=0),
                RangeValidator(range_criteria),
            ),
        ),

        TWO_FINGER_TRACKING:
        Gesture(
            name=TWO_FINGER_TRACKING,
            variations=((GV.LR, GV.RL, GV.TB, GV.BT, GV.BLTR, GV.TRBL),
                        (GV.SLOW, GV.NORMAL),
            ),
            prompt='Use two fingers to draw {0} lines {1} using a ruler '
                   'in {2}.',
            subprompt={
                GV.LR: ('horizontal', 'from left edge to right edge',),
                GV.RL: ('horizontal', 'from right edge to left edge',),
                GV.TB: ('vertical', 'from top edge to bottom edge',),
                GV.BT: ('vertical', 'from bottom edge to top edge',),
                GV.BLTR: ('diagonal', 'from bottom left to top right',),
                GV.TRBL: ('diagonal', 'from top right to bottom left',),
                GV.SLOW: ('3 seconds',),
                GV.NORMAL: ('1 second',),
            },
            validators=(
                CountTrackingIDValidator('== 2'),
                LinearityValidator(linearity_criteria, slot=0),
                LinearityValidator(linearity_criteria, slot=1),
                NoGapValidator(no_gap_criteria, slot=0),
                NoGapValidator(no_gap_criteria, slot=1),
                NoReversedMotionValidator(no_reversed_motion_criteria,
                                          slots=(0, 1)),
            ),
        ),

        FINGER_CROSSING:
        Gesture(
            # also covers stationary_finger_not_affected_by_2nd_moving_finger
            name=FINGER_CROSSING,
            variations=((GV.LR, GV.RL, GV.TB, GV.BT, GV.BLTR, GV.TRBL),
                        (GV.SLOW, GV.NORMAL),
            ),
            prompt='The 1st finger touches the center of the touchpad. '
                   'The 2nd finger moves {0} {1} in {2}.',
            subprompt={
                GV.LR: ('from left to right', 'above the 1st finger'),
                GV.RL: ('from right to left', 'below the 1st finger'),
                GV.TB: ('from top to bottom', 'on the right to the 1st finger'),
                GV.BT: ('from bottom to top', 'on the left to the 1st finger'),
                GV.BLTR: ('from bottom left to top right',
                          'above the 1st finger',),
                GV.TRBL: ('from top right to bottom left',
                          'below the 1st finger'),
                GV.SLOW: ('3 seconds',),
                GV.NORMAL: ('1 second',),
            },
            validators=(
                CountTrackingIDValidator('== 2'),
                NoGapValidator(no_gap_criteria, slot=1),
                NoReversedMotionValidator(no_reversed_motion_criteria, slots=1),
                StationaryFingerValidator(stationary_finger_criteria, slot=0),
            ),
        ),

        ONE_FINGER_SWIPE:
        Gesture(
            name=ONE_FINGER_SWIPE,
            variations=(GV.BLTR, GV.TRBL),
            prompt='Use a finger to swipe quickly {0}.',
            subprompt={
                GV.BLTR: ('from bottom left to top right',),
                GV.TRBL: ('from top right to bottom left',),
            },
            validators=(
                CountPacketsValidator(count_packets_criteria, slot=0),
                CountTrackingIDValidator('== 1'),
                NoReversedMotionValidator(no_reversed_motion_criteria, slots=0),
            ),
        ),

        TWO_FINGER_SWIPE:
        Gesture(
            name=TWO_FINGER_SWIPE,
            variations=(GV.TB, GV.BT),
            prompt='Use two fingers to swipe quickly {0}.',
            subprompt={
                GV.TB: ('from top to bottom',),
                GV.BT: ('from bottom to top',),
            },
            validators=(
                CountPacketsValidator(count_packets_criteria, slot=0),
                CountPacketsValidator(count_packets_criteria, slot=1),
                CountTrackingIDValidator('== 2'),
                NoReversedMotionValidator(no_reversed_motion_criteria,
                                          slots=(0, 1)),
            ),
        ),

        PINCH_TO_ZOOM:
        Gesture(
            name=PINCH_TO_ZOOM,
            variations=(GV.ZOOM_IN, GV.ZOOM_OUT),
            prompt='Use two fingers to pinch to {0} by drawing {1}.',
            subprompt={
                GV.ZOOM_IN: ('zoom in', 'farther'),
                GV.ZOOM_OUT: ('zoom out', 'closer'),
            },
            validators=(
                CountTrackingIDValidator('== 2'),
                PinchValidator(pinch_criteria)
            ),
        ),

        ONE_FINGER_TAP:
        Gesture(
            name=ONE_FINGER_TAP,
            variations=(GV.TL, GV.TR, GV.BL, GV.BR, GV.TS, GV.BS, GV.LS, GV.RS,
                        GV.CENTER),
            prompt='Use one finger to make a tap on the {0} of the pad.',
            subprompt={
                GV.TL: ('top left corner',),
                GV.TR: ('top right corner',),
                GV.BL: ('bottom left corner',),
                GV.BR: ('bottom right corner',),
                GV.TS: ('top side',),
                GV.BS: ('bottom side',),
                GV.LS: ('left hand side',),
                GV.RS: ('right hand side',),
                GV.CENTER: ('center',),
            },
            validators=(
                CountTrackingIDValidator('== 1'),
                PhysicalClickValidator('== 0', fingers=1),
                PhysicalClickValidator('== 0', fingers=2),
                StationaryFingerValidator(stationary_finger_criteria, slot=0),
            ),
        ),

        TWO_FINGER_TAP:
        Gesture(
            name=TWO_FINGER_TAP,
            variations=(GV.HORIZONTAL, GV.VERTICAL, GV.DIAGONAL),
            prompt='Use two fingers aligned {0} to make a tap.',
            subprompt={
                GV.HORIZONTAL: ('horizontally',),
                GV.VERTICAL: ('vertically',),
                GV.DIAGONAL: ('diagonally',),
            },
            validators=(
                CountTrackingIDValidator('== 2'),
                PhysicalClickValidator('== 0', fingers=1),
                PhysicalClickValidator('== 0', fingers=2),
                StationaryFingerValidator(stationary_finger_criteria, slot=0),
                StationaryFingerValidator(stationary_finger_criteria, slot=1),
            ),
        ),

        ONE_FINGER_PHYSICAL_CLICK:
        Gesture(
            name=ONE_FINGER_PHYSICAL_CLICK,
            variations=None,
            prompt='Use one finger to make 1 physical click.',
            subprompt=None,
            validators=(
                CountTrackingIDValidator('== 1'),
                PhysicalClickValidator('== 1', fingers=1),
                StationaryFingerValidator(stationary_finger_criteria, slot=0),
            ),
        ),

        TWO_FINGER_PHYSICAL_CLICK:
        Gesture(
            name=TWO_FINGER_PHYSICAL_CLICK,
            variations=None,
            prompt='Use two fingers to make 1 physical click.',
            subprompt=None,
            validators=(
                CountTrackingIDValidator('== 2'),
                PhysicalClickValidator('== 1', fingers=2),
                StationaryFingerValidator(stationary_finger_criteria, slot=0),
                StationaryFingerValidator(stationary_finger_criteria, slot=1),
            ),
        ),

        THREE_FINGER_PHYSICAL_CLICK:
        Gesture(
            name=THREE_FINGER_PHYSICAL_CLICK,
            variations=None,
            prompt='Use three fingers to make 1 physical click.',
            subprompt=None,
            validators=(
                CountTrackingIDValidator('== 3'),
                PhysicalClickValidator('== 1', fingers=3),
                StationaryFingerValidator(stationary_finger_criteria, slot=0),
                StationaryFingerValidator(stationary_finger_criteria, slot=1),
                StationaryFingerValidator(stationary_finger_criteria, slot=2),
            ),
        ),

        FOUR_FINGER_PHYSICAL_CLICK:
        Gesture(
            name=FOUR_FINGER_PHYSICAL_CLICK,
            variations=None,
            prompt='Use four fingers to make 1 physical click.',
            subprompt=None,
            validators=(
                CountTrackingIDValidator('== 4'),
                PhysicalClickValidator('== 1', fingers=4),
                StationaryFingerValidator(stationary_finger_criteria, slot=0),
                StationaryFingerValidator(stationary_finger_criteria, slot=1),
                StationaryFingerValidator(stationary_finger_criteria, slot=2),
                StationaryFingerValidator(stationary_finger_criteria, slot=3),
            ),
        ),

        FIVE_FINGER_PHYSICAL_CLICK:
        Gesture(
            name=FIVE_FINGER_PHYSICAL_CLICK,
            variations=None,
            prompt='Use five fingers to make 1 physical click.',
            subprompt=None,
            validators=(
                CountTrackingIDValidator('== 5'),
                PhysicalClickValidator('== 1', fingers=5),
                StationaryFingerValidator(stationary_finger_criteria, slot=0),
                StationaryFingerValidator(stationary_finger_criteria, slot=1),
                StationaryFingerValidator(stationary_finger_criteria, slot=2),
                StationaryFingerValidator(stationary_finger_criteria, slot=3),
                StationaryFingerValidator(stationary_finger_criteria, slot=4),
            ),
        ),

        STATIONARY_FINGER_NOT_AFFECTED_BY_2ND_FINGER_TAPS:
        Gesture(
            name=STATIONARY_FINGER_NOT_AFFECTED_BY_2ND_FINGER_TAPS,
            variations=(GV.AROUND,),
            prompt='Place your left finger on the middle of the pad. '
                   'And use 2nd finger to tap around the first finger',
            subprompt=None,
            validators=(
                CountTrackingIDValidator('>= 2'),
                StationaryFingerValidator(stationary_finger_criteria, slot=0),
            ),
        ),

        FAT_FINGER_MOVE_WITH_RESTING_FINGER:
        Gesture(
            name=FAT_FINGER_MOVE_WITH_RESTING_FINGER,
            variations=(GV.LR, GV.RL, GV.TB, GV.BT),
            prompt='With a stationary finger resting on the {0} of the pad, '
                   'the 2nd FAT finger moves {1} {2} the first finger.',
            subprompt={
                GV.LR: ('center', 'from left to right', 'below'),
                GV.RL: ('bottom', 'from right to left', 'above'),
                GV.TB: ('center', 'from top to bottom', 'on the right to'),
                GV.BT: ('center', 'from bottom to top', 'on the left to'),
            },
            validators=(
                CountTrackingIDValidator('== 2'),
                LinearityValidator(linearity_criteria, slot=1),
                NoGapValidator(no_gap_criteria, slot=1),
                NoReversedMotionValidator(no_reversed_motion_criteria, slots=1),
                StationaryFingerValidator(stationary_finger_criteria, slot=0),
            ),
        ),

        DRAG_EDGE_THUMB:
        Gesture(
            name=DRAG_EDGE_THUMB,
            variations=(GV.LR, GV.RL, GV.TB, GV.BT),
            prompt='Drag the edge of your thumb {0} across the pad',
            subprompt={
                GV.LR: ('horizontally from left to right',),
                GV.RL: ('horizontally from right to left',),
                GV.TB: ('vertically from top to bottom',),
                GV.BT: ('vertically from bottom to top',),
            },
            validators=(
                CountTrackingIDValidator('== 1'),
                LinearityValidator(linearity_criteria, slot=0),
                NoGapValidator(no_gap_criteria, slot=0),
                NoReversedMotionValidator(no_reversed_motion_criteria, slots=0),
            ),
        ),

        TWO_CLOSE_FINGERS_TRACKING:
        Gesture(
            # TODO(josephsih): make a special two-finger pen to perform this
            # gesture so that the finger distance remains the same every time
            # this test is conducted.
            name=TWO_CLOSE_FINGERS_TRACKING,
            variations=(GV.LR, GV.TB, GV.TLBR),
            prompt='With two fingers close together (lightly touching each '
                   'other) in a two finger scrolling gesture, draw a {0} '
                   'line {1}.',
            subprompt={
                GV.LR: ('horizontal', 'from left to right',),
                GV.TB: ('vertical', 'from top to bottom',),
                GV.TLBR: ('diagonal', 'from top left to bottom right',),
            },
            validators=(
                CountTrackingIDValidator('== 2'),
                LinearityValidator(linearity_criteria, slot=0),
                NoGapValidator(no_gap_criteria, slot=0),
                NoReversedMotionValidator(no_reversed_motion_criteria, slots=0),
            ),
        ),

        RESTING_FINGER_PLUS_2ND_FINGER_MOVE:
        Gesture(
            name=RESTING_FINGER_PLUS_2ND_FINGER_MOVE,
            variations=((GV.TLBR, GV.BRTL),
                        (GV.SLOW,),
            ),
            prompt='With a stationary finger resting on the bottom left corner,'
                   ' the 2nd finger moves {0} in {1}.',
            subprompt={
                GV.TLBR: ('from top left to bottom right',),
                GV.BRTL: ('from bottom right to top left',),
                GV.SLOW: ('3 seconds',),
            },
            validators=(
                CountTrackingIDValidator('== 2'),
                LinearityValidator(linearity_criteria, slot=1),
                NoGapValidator(no_gap_criteria, slot=1),
                NoReversedMotionValidator(no_reversed_motion_criteria, slots=1),
                StationaryFingerValidator(stationary_finger_criteria, slot=0),
            ),
        ),

        TWO_FAT_FINGERS_TRACKING:
        Gesture(
            name=TWO_FAT_FINGERS_TRACKING,
            variations=(GV.LR, GV.RL),
            prompt='Place two FAT fingers separated by about 1 cm on the pad '
                'next to each other. Move {0} with the two fingers.',
            subprompt={
                GV.LR: ('from left to right',),
                GV.RL: ('from right to left',),
            },
            validators=(
                CountTrackingIDValidator('== 2'),
                LinearityValidator(linearity_criteria, slot=0),
                LinearityValidator(linearity_criteria, slot=1),
                NoGapValidator(no_gap_criteria, slot=0),
                NoGapValidator(no_gap_criteria, slot=1),
                NoReversedMotionValidator(no_reversed_motion_criteria, slots=0),
                NoReversedMotionValidator(no_reversed_motion_criteria, slots=1),
            ),
        ),

        FIRST_FINGER_TRACKING_AND_SECOND_FINGER_TAPS:
        Gesture(
            name=FIRST_FINGER_TRACKING_AND_SECOND_FINGER_TAPS,
            variations=(GV.TLBR, GV.BRTL),
            prompt='A finger moves {0} slowly in 3 seconds. '
                   'Without the 1st finger leaving the pad, '
                   'the 2nd finger taps gently for 3 times.',
            subprompt={
                GV.TLBR: ('from top left to bottom right',),
                GV.BRTL: ('from bottom right to top left',),
            },
            validators=(
                CountTrackingIDValidator('== 4'),
                LinearityValidator(linearity_criteria, slot=0),
                NoGapValidator(no_gap_criteria, slot=0),
                NoReversedMotionValidator(no_reversed_motion_criteria, slots=0),
            ),
        ),

        DRUMROLL:
        Gesture(
            name=DRUMROLL,
            variations=(GV.FAST, GV.NORMAL, GV.SLOW),
            prompt='Use two fingers to make drum roll {0} for a total of '
                   '5 seconds.',
            subprompt={
                GV.SLOW: ('at about 1 tap per second',),
                GV.NORMAL: ('at about 2 taps per second',),
                GV.FAST: ('as fast as possible',),
            },
            validators=(
                CountTrackingIDValidator('>= 5'),
                DrumrollValidator(drumroll_criteria),
            ),
            timeout = 2000,
        ),
    }
    return gesture_dict


class FileName:
    """A dummy class to hold the attributes in a test file name."""
    pass
filename = FileName()
filename.sep = '-'
filename.ext = 'dat'


class Gesture:
    """A class defines the structure of Gesture."""
    # define the default timeout (in milli-seconds) when performing a gesture.
    # A gesture is considered done when finger is lifted for this time interval.
    TIMEOUT = int(1000/80*10)

    def __init__(self, name=None, variations=None, prompt=None, subprompt=None,
                 validators=None, touchpad_edge=False, timeout=TIMEOUT):
        self.name = name
        self.variations = variations
        self.prompt = prompt
        self.subprompt = subprompt
        self.validators = validators
        self.touchpad_edge = touchpad_edge
        self.timeout = timeout
