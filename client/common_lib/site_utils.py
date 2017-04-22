# Copyright 2017 The Chromium OS Authors. All rights reserved.
# Use of this source code is governed by a BSD-style license that can be
# found in the LICENSE file.

"""This module is a hack for backward compatibility.

The real utils module is utils.py
"""

import warnings

from .utils import *


warnings.warn(
    '%s module is deprecated;'
    ' use the equivalent utils module instead'
    % __name__)
