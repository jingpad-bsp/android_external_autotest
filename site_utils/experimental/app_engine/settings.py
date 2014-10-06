#!/usr/bin/python
#
# Copyright (c) 2011 The Chromium OS Authors. All rights reserved.
# Use of this source code is governed by a BSD-style license that can be
# found in the LICENSE file.

__author__ = 'ericli@chromium.org (Eric Li)'

import time

DEFAULT_TABLE_ROWS='10'
DEFAULT_BOARD='x86-alex-r13'
DEFAULT_NETBOOK='ALEX'
DEFAULT_PUBLIC_NETBOOK='CR-48'
DEFAULT_BOARD_ORDER = ('x86-alex-r13,x86-alex-r12,x86-alex-r11,'
                       'x86-mario-r13,x86-mario-r12,x86-mario-r11,'
                       'x86-zgb-r13,tegra2_kaen-rc,tegra2_seaboard-rc')
DEFAULT_CATEGORIES = 'bvt'
DEFAULT_CATEGORY = 'bvt'
EXTRA_CATEGORIES = ["browsertest", "bvt", "flaky", "hwqual", "network_3g",
                    "pagecycler", "pyauto", "sync", "regression"]

COLOR_GREEN = '#32CD32'
COLOR_ORANGE = '#FF8040'
COLOR_RED = '#FF4040'
COLOR_GRAY = '#E5E5C0'

MAX_BUILDS = 100        # How many builds per board we will keep in db.
DEFAULT_LENGTH = 15
DEFAULT_TABLE_HEADER_HEIGHT = 150

IN_QUERY_LIMIT = 30
# what is a better way to compute off PST DST?
TIMEZONE_OFFSET = (time.daylight + 7) * 3600
