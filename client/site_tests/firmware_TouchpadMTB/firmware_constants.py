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
X = 0
Y = 1

# Constants about gesture variations
HORIZONTAL = 'horizontal'
VERTICAL = 'vertical'
DIAGONAL = 'diagonal'

# Constants about fuzzy membership functions
# In fuzzy logic, a membership function indicates the degree of truth
# which maps an input set to a grade in the real unit interval [0, 1].
PI_FUNCTION = 'Pi_Function'
S_FUNCTION = 'S_Function'
Z_FUNCTION = 'Z_Function'
SINGLETON_FUNCTION = 'Singleton_Function'
TRAPEZ_FUNCTION = 'Trapez_Function'
TRIANGLE_FUNCTION = 'Triangle_Function'
