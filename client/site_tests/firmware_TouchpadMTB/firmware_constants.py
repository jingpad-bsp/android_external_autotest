# Copyright (c) 2012 The Chromium OS Authors. All rights reserved.
# Use of this source code is governed by a BSD-style license that can be
# found in the LICENSE file.

"""Define constants for firmware touchpad MTB tests."""


class _ConstantError(AttributeError):
    """A constant error exception."""
    pass


class _Constant(object):
    """This is a constant base class to ensure no rebinding of constants."""
    def __setattr__(self, name, value):
        """Check the attribute assignment. No rebinding is allowed."""
        if name in self.__dict__:
            raise _ConstantError, "Cannot rebind the constant: %s" % name
        self.__dict__[name] = value


"""Define constants classes in alphabetic order below."""


class _Axis(_Constant):
    """Constants about two axes."""
    pass
AXIS = _Axis()
AXIS.X = 'X'
AXIS.Y = 'Y'


class _Fuzzy_MF(_Constant):
    """Constants about fuzzy membership functions."""
    pass
MF = _Fuzzy_MF()
MF.PI_FUNCTION = 'Pi_Function'
MF.S_FUNCTION = 'S_Function'
MF.SINGLETON_FUNCTION = 'Singleton_Function'
MF.TRAPEZ_FUNCTION = 'Trapez_Function'
MF.TRIANGLE_FUNCTION = 'Triangle_Function'
MF.Z_FUNCTION = 'Z_Function'


class _GestureVariation(_Constant):
    """Constants about gesture variations."""
    pass
GV = _GestureVariation()
# constants about directions
GV.HORIZONTAL = 'horizontal'
GV.VERTICAL = 'vertical'
GV.DIAGONAL = 'diagonal'
GV.LR = 'left_to_right'
GV.RL = 'right_to_left'
GV.TB = 'top_to_bottom'
GV.BT = 'bottom_to_top'
GV.BLTR = 'bottom_left_to_top_right'
GV.BRTL = 'bottom_right_to_top_left'
GV.TRBL = 'top_right_to_bottom_left'
GV.TLBR = 'top_left_to_bottom_right'
GV.HORIZONTAL_DIRECTIONS = [GV.HORIZONTAL, GV.LR, GV.RL]
GV.VERTICAL_DIRECTIONS = [GV.VERTICAL, GV.TB, GV.BT]
GV.DIAGONAL_DIRECTIONS = [GV.DIAGONAL, GV.BLTR, GV.BRTL, GV.TRBL, GV.TLBR]
GV.GESTURE_DIRECTIONS = (GV.HORIZONTAL_DIRECTIONS + GV.VERTICAL_DIRECTIONS +
                         GV.DIAGONAL_DIRECTIONS)
# constants about locations
GV.TL = 'top_left'
GV.TR = 'top_right'
GV.BL = 'bottom_left'
GV.BR = 'bottom_right'
GV.TS = 'top_side'
GV.BS = 'bottom_side'
GV.LS = 'left_side'
GV.RS = 'right_side'
GV.CENTER = 'center'
GV.GESTURE_LOCATIONS = [GV.TL, GV.TR, GV.BL, GV.BR, GV.TS, GV.BS, GV.LS, GV.RS,
                        GV.CENTER]
# constants about pinch to zoom
GV.ZOOM_IN = 'zoom_in'
GV.ZOOM_OUT = 'zoom_out'
# constants about speed
GV.SLOW = 'slow'
GV.NORMAL = 'normal'
GV.FAST = 'fast'
GV.GESTURE_SPEED = [GV.SLOW, GV.NORMAL, GV.FAST]


class _Mode(_Constant):
    """Constants about gesture playing mode."""
    pass
MODE = _Mode()
MODE.MANUAL = 'MANUAL'
MODE.REPLAY = 'REPLAY'
MODE.ROBOT = 'ROBOT'
MODE.GESTURE_PLAY_MODE = [MODE.MANUAL, MODE.ROBOT, MODE.REPLAY]


class _MTB(_Constant):
    """Constants about MTB event format."""
    pass
MTB = _MTB()
MTB.EV_TIME = 'EV_TIME'
MTB.EV_TYPE = 'EV_TYPE'
MTB.EV_CODE = 'EV_CODE'
MTB.EV_VALUE = 'EV_VALUE'
MTB.SYN_REPORT = 'SYN_REPORT'


class _Options(_Constant):
    """Constants about command line options."""
    pass
OPTIONS = _Options()
OPTIONS.HELP = 'help'
OPTIONS.MODE = 'mode'
OPTIONS.SIMPLIFIED = 'simplified'
