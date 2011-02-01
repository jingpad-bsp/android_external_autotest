# Copyright (c) 2010 The Chromium OS Authors. All rights reserved.
# Use of this source code is governed by a BSD-style license that can be
# found in the LICENSE file.

import os, sys
from autotest_lib.client.cros import constants

sys.path.append(os.environ.get("SYSROOT", "/usr/local/") +
                constants.FLIMFLAM_TEST_PATH)
