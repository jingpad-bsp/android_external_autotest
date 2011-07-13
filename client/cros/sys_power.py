#!/usr/bin/python

# Copyright (c) 2010 The Chromium OS Authors. All rights reserved.
# Use of this source code is governed by a BSD-style license that can be
# found in the LICENSE file.

# NB: this code is downloaded for use by site_system_suspend.py;
# beware of adding dependencies on client libraries such as utils

"""Provides utility methods for controlling powerd in ChromiumOS.
"""

import os

SUSPEND_CMD='/usr/bin/powerd_suspend'
REQUEST_SUSPEND_CMD = ('/usr/bin/dbus-send --system /'
                       'org.chromium.PowerManager.RequestSuspend')

def set_state(state):
    """
    Set the system power state to 'state'.
    """
    file('/sys/power/state', 'w').write("%s\n" % state)


def suspend_to_ram():
    """
    Suspend the system to RAM (S3)
    """
    if os.path.exists(SUSPEND_CMD):
        os.system(SUSPEND_CMD)
    else:
        set_power_state('mem')


def suspend_to_disk():
    """
    Suspend the system to disk (S4)
    """
    set_power_state('disk')

def standby():
    """
    Power-on suspend (S1)
    """
    set_power_state('standby')

def request_suspend():
    """
    Requests that powerd suspend the machine using the same path as if
    the users had requested a suspend.  This will disconnect the
    modem, lock the screen, etc.
    """
    os.system(REQUEST_SUSPEND_CMD)
