# Copyright (c) 2012 The Chromium OS Authors. All rights reserved.
# Use of this source code is governed by a BSD-style license that can be
# found in the LICENSE file.
import logging, os, re
from autotest_lib.client.bin import utils

def get_x86_cpu_arch():
    """Identify CPU architectural type.

    Intel's processor naming conventions is a mine field of inconsistencies.
    Armed with that, this method simply tries to identify the architecture of
    systems we care about.

    TODO(tbroch) grow method to cover processors numbers outlined in:
        http://www.intel.com/content/www/us/en/processors/processor-numbers.html
        perhaps returning more information ( brand, generation, features )

    Returns:
      String, explicitly (Atom, Core, Celeron) or None
    """
    cpuinfo = utils.read_file('/proc/cpuinfo')

    if re.search(r'Intel.*Atom.*[NZ][2-6]', cpuinfo):
        return 'Atom'
    if re.search(r'Intel.*Celeron.*8[1456][07]', cpuinfo):
        return 'Celeron'
    if re.search(r'Intel.*Core.*i[357]-[23][0-9][0-9][0-9]', cpuinfo):
        return 'Core'

    logging.info(cpuinfo)
    return None


def has_rapl_support():
    """Identify if platform supports Intels RAPL subsytem.

    Returns:
        Boolean, True if RAPL supported, False otherwise.
    """
    cpu_arch = get_x86_cpu_arch()
    if cpu_arch and ((cpu_arch is 'Celeron') or (cpu_arch is 'Core')):
        return True
    return False


class KbdBacklightException(Exception):
    """Class for KbdBacklight exceptions."""


class KbdBacklight(object):
    """Class for control of keyboard backlight.

    Example code:
        kblight = power_utils.KbdBacklight()
        kblight.set(10)
        print "kblight % is %.f" % kblight.get()

    Public methods:
        set: Sets the keyboard backlight to a percent.
        get: Get current keyboard backlight percentage.

    Private functions:
        _get_max: Retrieve maximum integer setting of keyboard backlight

    Private attributes:
        _path: filepath to keyboard backlight controls in sysfs
        _max: cached value of 'max_brightness' integer

    TODO(tbroch): deprecate direct sysfs access if/when these controls are
    integrated into a userland tool such as backlight-tool in power manager.
    """
    DEFAULT_PATH = "/sys/class/leds/chromeos::kbd_backlight"

    def __init__(self, path=DEFAULT_PATH):
        if not os.path.exists(path):
            raise KbdBacklightException('Unable to find path "%s"' % path)
        self._path = path
        self._max = None


    def _get_max(self):
        """Get maximum absolute value of keyboard brightness.

        Returns:
            integer, maximum value of keyboard brightness
        """
        if self._max is None:
            self._max = int(utils.read_one_line(os.path.join(self._path,
                                                             'max_brightness')))
        return self._max


    def get(self):
        """Get current keyboard brightness setting.

        Returns:
            float, percentage of keyboard brightness.
        """
        current = int(utils.read_one_line(os.path.join(self._path,
                                                       'brightness')))
        return (current * 100 ) / self._get_max()


    def set(self, percent):
        """Set keyboard backlight percent.

        Args:
            percent: percent to set keyboard backlight to.
        """
        value = int((percent * self._get_max()) / 100)
        cmd = "echo %d > %s" % (value, os.path.join(self._path, 'brightness'))
        utils.system(cmd)
