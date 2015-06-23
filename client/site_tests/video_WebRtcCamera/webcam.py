# Copyright 2015 The Chromium OS Authors. All rights reserved.
# Use of this source code is governed by a BSD-style license that can be
# found in the LICENSE file.
import re

from autotest_lib.client.bin import utils
from autotest_lib.client.common_lib import error


def supports_720p():
    """Checks if 720p capture supported.

    @returns: True if 720p supported, false if VGA is supported.
    @raises: TestError if neither 720p nor VGA are supported.
    """
    cmd = 'lsusb -v'
    # Get usb devices and make output a string with no newline marker.
    usb_devices = utils.system_output(cmd, ignore_status=True).splitlines()
    usb_devices = ''.join(usb_devices)

    # Check if 720p resolution supported.
    if re.search(r'\s+wWidth\s+1280\s+wHeight\s+720', usb_devices):
        return True
    # The device should support at least VGA.
    # Otherwise the cam must be broken.
    if re.search(r'\s+wWidth\s+640\s+wHeight\s+480', usb_devices):
        return False
    # This should not happen.
    raise error.TestFail(
            'Could not find any cameras reporting '
            'either VGA or 720p in lsusb output: %s' % usb_devices)

