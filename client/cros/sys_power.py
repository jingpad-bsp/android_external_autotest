# Copyright (c) 2012 The Chromium OS Authors. All rights reserved.
# Use of this source code is governed by a BSD-style license that can be
# found in the LICENSE file.

# NB: this code is downloaded for use by site_system_suspend.py;
# beware of adding dependencies on client libraries such as utils

"""Provides utility methods for controlling powerd in ChromiumOS.
"""

import os, upstart


SUSPEND_CMD='/usr/bin/powerd_suspend'
REQUEST_SUSPEND_CMD = ('/usr/bin/dbus-send --system / '
                       'org.chromium.PowerManager.RequestSuspend')

SUSPEND_RESUME_MESSAGES = {
    'START_SUSPEND':['Freezing user space'],
    'END_SUSPEND':['Back to C!', 'Low-level resume complete',
                   'Entering suspend state', 'sleep: irq wakeup masks:'],
    'START_RESUME':['Back to C!', 'Low-level resume complete', 'Suspended for',
                    'Resume caused by', 'post sleep, preparing to return'],
    'END_RESUME':['Restarting tasks'],
    }


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
        os.system(SUSPEND_CMD + ' --test')
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
    for service_name in ['powerd', 'powerm']:
        upstart.ensure_running(service_name)

    os.system(REQUEST_SUSPEND_CMD)
