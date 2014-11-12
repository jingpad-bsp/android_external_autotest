# Copyright 2014 The Chromium OS Authors. All rights reserved.
# Use of this source code is governed by a BSD-style license that can be
# found in the LICENSE file.

import os.path

def privetd_is_installed():
    """@return True iff privetd is installed in this system."""
    if os.path.exists('/usr/bin/privetd'):
        return True
    return False
