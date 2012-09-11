# Copyright (c) 2012 The Chromium OS Authors. All rights reserved.
# Use of this source code is governed by a BSD-style license that can be
# found in the LICENSE file.

"""Some constants for firmware touchpad MTB tests."""

# Constants about MTB event format
EV_TIME = 'EV_TIME'
EV_TYPE = 'EV_TYPE'
EV_CODE = 'EV_CODE'
EV_VALUE = 'EV_VALUE'
SYN_REPORT = 'SYN_REPORT'

# Constants about two axes
X = 'X'
Y = 'Y'

# Constants about gesture variations
# Directions
HORIZONTAL = 'horizontal'
VERTICAL = 'vertical'
DIAGONAL = 'diagonal'
LR = 'left_to_right'
RL = 'right_to_left'
TB = 'top_to_bottom'
BT = 'bottom_to_top'
BLTR = 'bottom_left_to_top_right'
BRTL = 'bottom_right_to_top_left'
TRBL = 'top_right_to_bottom_left'
TLBR = 'top_left_to_bottom_right'
HORIZONTAL_DIRECTIONS = [HORIZONTAL, LR, RL]
VERTICAL_DIRECTIONS = [VERTICAL, TB, BT]
DIAGONAL_DIRECTIONS = [DIAGONAL, BLTR, BRTL, TRBL, TLBR]
# location
TL = 'top_left'
TR = 'top_right'
BL = 'bottom_left'
BR = 'bottom_right'
TS = 'top_side'
BS = 'bottom_side'
LS = 'left_side'
RS = 'right_side'
CENTER = 'center'
# pinch to zoom
ZOOM_IN = 'zoom_in'
ZOOM_OUT = 'zoom_out'
# Speed
SLOW = 'slow'
NORMAL = 'normal'
FAST = 'fast'

# Constants about fuzzy membership functions
# In fuzzy logic, a membership function indicates the degree of truth
# which maps an input set to a grade in the real unit interval [0, 1].
PI_FUNCTION = 'Pi_Function'
S_FUNCTION = 'S_Function'
Z_FUNCTION = 'Z_Function'
SINGLETON_FUNCTION = 'Singleton_Function'
TRAPEZ_FUNCTION = 'Trapez_Function'
TRIANGLE_FUNCTION = 'Triangle_Function'
