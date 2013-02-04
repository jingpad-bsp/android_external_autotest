# Copyright (c) 2011 The Chromium OS Authors. All rights reserved.
# Use of this source code is governed by a BSD-style license that can be
# found in the LICENSE file.

# NB: this code is downloaded for use by site_system_suspend.py;
# beware of adding dependencies on client libraries such as utils

"""Provides utility methods for interacting with upstart"""

import os

def ensure_running(service_name):
    cmd = 'initctl status %s | grep start/running' % service_name
    os.system(cmd)
