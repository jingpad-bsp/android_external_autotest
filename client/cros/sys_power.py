# Copyright (c) 2012 The Chromium OS Authors. All rights reserved.
# Use of this source code is governed by a BSD-style license that can be
# found in the LICENSE file.

# NB: this code is downloaded for use by site_system_suspend.py;
# beware of adding dependencies on client libraries such as utils

"""Provides utility methods for controlling powerd in ChromiumOS."""

import errno, logging, os, rtc, upstart

SYSFS_POWER_STATE = '/sys/power/state'
SYSFS_WAKEUP_COUNT = '/sys/power/wakeup_count'


class SuspendFailure(Exception):
    """Base class for a failure during a single suspend/resume cycle."""
    pass


class SuspendAbort(SuspendFailure):
    """Suspend took too long, got wakeup event (RTC tick) before it was done."""
    pass


class KernelError(SuspendFailure):
    """Kernel problem encountered during suspend/resume."""
    pass


class FirmwareError(SuspendFailure):
    """String 'ERROR' found in firmware log after resume."""
    WHITELIST = [r'PNP: 002e\.4 70 irq size: 0x0000000001 not assigned']


class EarlyWakeupError(SuspendFailure):
    """Unexpected early wakeup from suspend (spurious interrupts?)."""
    pass


class MemoryError(SuspendFailure):
    """memory_suspend_test found memory corruption."""
    pass


def prepare_wakeup(seconds):
    wakeup_count = read_wakeup_count()
    alarm = int(rtc.get_seconds() + seconds)
    logging.debug('Suspend for %d seconds, wakealarm = %d' % (seconds, alarm))
    rtc.set_wake_alarm(alarm)
    return (alarm, wakeup_count)


def check_wakeup(alarm):
    now = rtc.get_seconds()
    if now < alarm:
        logging.error('Woke up early at %d', now)
        raise EarlyWakeupError('Woke from suspend early')


def dbus_suspend(seconds):
    """
    Suspend the system to RAM (S3), waking up again after |seconds|, using
    the powerd_dbus_suspend script. System must be logged in as a non-guest
    user for this to work. Function will block until suspend/resume has
    completed or failed. Returns the wake alarm time from the RTC as epoch.
    """
    alarm = prepare_wakeup(seconds)[0]
    upstart.ensure_running(['powerd', 'powerm'])
    os.system('/usr/bin/powerd_dbus_suspend --timeout 30')
    check_wakeup(alarm)
    return alarm


def do_suspend(seconds):
    """
    Suspend the system to RAM (S3), waking up again after |seconds|, using
    the powerd_suspend script. Function will block until suspend/resume has
    completed or failed. Returns the wake alarm time from the RTC as epoch.
    """
    alarm, wakeup_count = prepare_wakeup(seconds)
    os.system('/usr/bin/powerd_suspend -w %d' % wakeup_count)
    check_wakeup(alarm)
    return alarm


def kernel_suspend(seconds):
    """
    Suspend the system to RAM (S3), waking up again after |seconds|, by directly
    writing to /sys/power/state. Function will block until suspend/resume has
    completed or failed.
    """
    alarm, wakeup_count = prepare_wakeup(seconds)
    logging.debug('Saving wakeup count: %d', wakeup_count)
    write_wakeup_count(wakeup_count)
    try:
        logging.info('Suspending at %d', rtc.get_seconds())
        with open(SYSFS_POWER_STATE, 'w') as sysfs_file:
            sysfs_file.write('mem')
    except IOError as e:
        logging.exception('Writing to %s failed' % SYSFS_POWER_STATE)
        if e.errno == errno.EBUSY and rtc.get_seconds() >= alarm:
            # The kernel returns EBUSY if it has to abort because
            # the RTC alarm fires before we've reached suspend.
            raise SuspendAbort('Suspend took too long, RTC alarm fired')
        else:
            # Some driver probably failed to suspend properly.
            # A hint as to what failed is in errno.
            raise KernelError('Suspend failed: %s' % e.strerror)
    else:
        logging.info('Woke from suspend at %d', rtc.get_seconds())
    logging.debug('New wakeup count: %d', read_wakeup_count())
    check_wakeup(alarm)


def memory_suspend(seconds, size):
    """
    Suspend the system to RAM (S3), waking up again after |seconds|, using
    the memory_suspend_test tool. Function will block until suspend/resume has
    completed or failed. Returns the wake alarm time from the RTC as epoch.
    """
    # since we cannot have utils.system_output in here, we need a workaround
    output = '/tmp/memory_suspend_output'
    alarm, wakeup_count = prepare_wakeup(seconds)
    status = os.system('/usr/bin/memory_suspend_test --wakeup_count %d '
                       '--size %d > %s' % (wakeup_count, size, output))
    status = os.WEXITSTATUS(status)
    if status == 2:
        logging.error('memory_suspend_test found the following errors:')
        for line in open(output, 'r'):
            logging.error(line)
        raise MemoryError('Memory corruption found after resume')
    elif status:
        raise SuspendFailure('Failure in powerd_suspend during memory test')
    check_wakeup(alarm)
    return alarm


def read_wakeup_count():
    """
    Retrieves the current value of /sys/power/wakeup_count.
    """
    with open(SYSFS_WAKEUP_COUNT) as sysfs_file:
        return int(sysfs_file.read().rstrip('\n'))


def write_wakeup_count(wakeup_count):
    """
    Writes a value to /sys/power/wakeup_count.
    """
    try:
        with open(SYSFS_WAKEUP_COUNT, 'w') as sysfs_file:
            sysfs_file.write(str(wakeup_count))
    except IOError as e:
        if (e.errno == errno.EINVAL and read_wakeup_count() != wakeup_count):
            raise SuspendAbort('wakeup_count changed before suspend')
        else:
            raise
