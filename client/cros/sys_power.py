# Copyright (c) 2012 The Chromium OS Authors. All rights reserved.
# Use of this source code is governed by a BSD-style license that can be
# found in the LICENSE file.

# NB: this code is downloaded for use by site_system_suspend.py;
# beware of adding dependencies on client libraries such as utils

"""Provides utility methods for controlling powerd in ChromiumOS.
"""

import errno, os, upstart, rtc
from autotest_lib.client.bin import utils


SUSPEND_CMD='/usr/bin/powerd_suspend'
REQUEST_SUSPEND_CMD = ('/usr/bin/dbus-send --system / '
                       'org.chromium.PowerManager.RequestSuspend')
SYSFS_WAKEUP_COUNT = '/sys/power/wakeup_count'


def set_state(state):
    """
    Set the system power state to 'state'.
    """
    file('/sys/power/state', 'w').write("%s\n" % state)


def suspend_to_ram(seconds=None):
    """
    Suspend the system to RAM (S3), optionally waking up after |seconds|
    """
    if seconds:
        now = rtc.get_seconds()
        rtc.set_wake_alarm(now + seconds)

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
    for service_name in ['powerd', 'powerm']:
        upstart.ensure_running(service_name)

    os.system(REQUEST_SUSPEND_CMD)


class ConcurrentWakeEventException(Exception):
    """
    The system wakeup count has changed from the value provided,
    meaning saving the count has raced with a wake event.
    """
    pass


def read_wakeup_count():
    """
    Retrieves the current value of /sys/power/wakeup_count.
    """
    wakeup_count = int(utils.read_file(SYSFS_WAKEUP_COUNT))
    return wakeup_count


def write_wakeup_count(wakeup_count):
    """
    Writes a value to /sys/power/wakeup_count.
    """
    try:
        utils.open_write_close(SYSFS_WAKEUP_COUNT, str(wakeup_count))
    except IOError as e:
        if (e.errno == errno.EINVAL and
                read_wakeup_count() != wakeup_count):
            raise ConcurrentWakeEventException()
        else:
            raise
