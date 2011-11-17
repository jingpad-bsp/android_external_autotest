#!/usr/bin/python
# Copyright (c) 2011 The Chromium OS Authors. All rights reserved.
# Use of this source code is governed by a BSD-style license that can be
# found in the LICENSE file.

"""Common utility functions that are not Trackpad specific.

These functions may be used by the Trackpad tests and record app.
"""

import logging
import subprocess


def simple_system(cmd):
    """Replace autotest utils.system() locally."""
    rc = subprocess.call(cmd, shell=True)
    if rc:
        logging.warning('Command (%s) failed (rc=%s).', cmd, rc)
    return rc


def simple_system_output(cmd):
    """Replace autotest utils.system_output() locally."""
    try:
        p = subprocess.Popen(cmd, shell=True, stdout=subprocess.PIPE,
                             stderr=subprocess.STDOUT)
        stdout, _ = p.communicate()
        if p.returncode:
            return None
        return stdout.strip()
    except Exception, e:
        logging.warning('Command (%s) failed (%s).', cmd, e)
