# Copyright (c) 2011 The Chromium OS Authors. All rights reserved.
# Use of this source code is governed by a BSD-style license that can be
# found in the LICENSE file.

"""
Helper server used for local debuggin of the HTML page on development machine.
This file does not run as part of the actual test on target device.
"""

import os
import sys

# paths are considered to be relative to
# src/third_party/autotest/files/client/site_tests/desktopui_TouchScreen

# httpd module lives here
sys.path.append(os.path.abspath('../../cros'))
import httpd


def url_handler(fh, form):
    print form.value
    print form.keys()


listener = httpd.HTTPListener(8000, docroot=os.path.abspath('.'))
listener.add_url_handler('/interaction/test', url_handler)
listener.run()
