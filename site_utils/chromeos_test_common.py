# Copyright (c) 2011 The Chromium OS Authors. All rights reserved.
# Use of this source code is governed by a BSD-style license that can be
# found in the LICENSE file.

"""A common helper that adds chromeos_test libraries to the path.

Also defines:
  chromeos_test_common.CURRENT_DIR as the current directory.
  chromeos_test_common.CRON_DIR as the autotest-tools/cron directory.
  chromeos_test_common.CROS_DIR as path to the ChromeOS enlistment.
"""

import os
import sys

# Figure out our absolute path so we can simplify configuration.
CURRENT_DIR = os.path.realpath(os.path.abspath(os.path.join(
    os.getcwd(), os.path.dirname(__file__))))
CROS_DIR = os.path.abspath(os.path.join(CURRENT_DIR, '../../../..'))
CRON_DIR = os.path.join(CURRENT_DIR, '../cron/')
sys.path.append(CRON_DIR)
