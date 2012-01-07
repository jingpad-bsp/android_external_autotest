# Copyright (c) 2012 The Chromium OS Authors. All rights reserved.
# Use of this source code is governed by a BSD-style license that can be
# found in the LICENSE file.

"""A container for constants shared among modules."""


class NOP:
    """A dummpy class to include NOP related constants for device events."""
    NOP = 'NOP'
    FINGER1_LANDED = '1st Finger Landed'
    FINGER1_LIFTED = '1st Finger Lifted'
    FINGER2_LANDED = '2nd Finger Landed'
    FINGER2_LIFTED = '2nd Finger Lifted'
    FINGER3_LANDED = '3rd Finger Landed'
    FINGER3_LIFTED = '3rd Finger Lifted'
    DEVICE_MOUSE_CLICK = 'Device Mouse Click'
    DEVICE_MOUSE_CLICK_PRESS = 'Device Mouse Click Press'
    DEVICE_MOUSE_CLICK_RELEASE = 'Device Mouse Click Release'
    TWO_FINGER_TOUCH = 'Two Finger Touch'
    pass
