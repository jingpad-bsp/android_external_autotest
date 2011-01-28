# Copyright (c) 2010 The Chromium OS Authors. All rights reserved.
# Use of this source code is governed by a BSD-style license that can
# be # found in the LICENSE file.

"""Provides utility methods for the Real Time Clock device.
"""

import errno


def get_seconds(utc=True):
    """
    Read the current time out of the RTC
    """
    return int(file('/sys/class/rtc/rtc0/since_epoch').readline())


def write_wake_alarm(alarm_time):
    """
    Write a value to the wake alarm
    """
    f = file('/sys/class/rtc/rtc0/wakealarm', 'w')
    f.write('%s\n' % str(alarm_time))
    f.close()

def set_wake_alarm(alarm_time):
    """
    Set the hardware RTC-based wake alarm to 'alarm_time'.
    """
    try:
        write_wake_alarm(alarm_time)
    except IOError as (errnum, strerror):
        if errnum != errno.EBUSY:
            raise
        write_wake_alarm('clear')
        write_wake_alarm(alarm_time)
        
