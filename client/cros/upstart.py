# Copyright (c) 2011 The Chromium OS Authors. All rights reserved.
# Use of this source code is governed by a BSD-style license that can be
# found in the LICENSE file.

"""Provides utility methods for interacting with upstart"""

import os

def ensure_running(service_name):
    cmd = 'initctl status %s | grep start/running' % service_name
    os.system(cmd)
