#!/usr/bin/env python
# Copyright (c) 2011 The Chromium OS Authors. All rights reserved.
# Use of this source code is governed by a BSD-style license that can be
# found in the LICENSE file.

'''Chrome OS device GPIO library

This module provides a convenient way to detect, setup, and access to GPIO
values on a Chrome OS compatible device.

See help(Gpio) for more information.

TODO(hungte) we need to handle the GPIO polarity in the future, or use the new
chromeos_acpi kernel mode module interface when it's done.
'''

import os
import shutil
import sys
import tempfile


CHROMEOS_HWID_FILEPATH = '/sys/devices/platform/chromeos_acpi/HWID'
CHROMEOS_FWID_FILEPATH = '/sys/devices/platform/chromeos_acpi/FWID'
GPIO_ATTR_ACTIVE_LOW = 0x00
GPIO_ATTR_ACTIVE_HIGH = 0x01
GPIO_ATTR_ACTIVE_MASK = 0x01
GPIO_NAME_DEVELOPER_SWITCH = 'developer_switch'
GPIO_NAME_RECOVERY_BUTTON = 'recovery_button'
GPIO_NAME_WRITE_PROTECT = 'write_protect'


class Gpio(object):
    '''
    Utility to access GPIO values.

    Usage:
        gpio = Gpio()
        try:
            gpio.setup()
            print gpio.read('developer_switch')
        except:
            print "gpio failed"
    '''

    def __init__(self, exception_type=IOError):
        self._gpio_root = None
        self._exception_type = exception_type
        self._override_attributes = {}

    def setup(self, gpio_root=None):
        '''Configures system for processing GPIO.

        Parameters:
            gpio_root: (optional) folder for symlinks to GPIO virtual files.

        Returns:
            Raises an exception if gpio_setup execution failed.
        '''
        if gpio_root:
            # Re-create if the folder already exists, because the symlinks may
            # be already changed.
            if os.path.exists(gpio_root):
                shutil.rmtree(gpio_root)
            os.mkdir(gpio_root)
        else:
            gpio_root = tempfile.mkdtemp()

        # The gpio_setup program detects GPIO devices files, and symlink them
        # into the specified folder. Then we can read the properties as file to
        # get the current GPIO value, ex $gpio_root/developer_switch.
        if os.system("gpio_setup --symlink_root='%s'" % gpio_root) != 0:
            raise self._exception_type('GPIO Setup Failed.')

        self._gpio_root = gpio_root

        # Customization by FWID
        with open(CHROMEOS_FWID_FILEPATH, 'r') as fwid_file:
            fwid = fwid_file.read()

        # TODO(hungte) Mario BIOS has a wrong polarity issue for write_protect,
        # at least up to 0038G6. Once it's fixed in some version, we need to fix
        # the list (or by HWID).
        if fwid.startswith('Mario.'):
            self._override_attributes = {
                GPIO_NAME_RECOVERY_BUTTON: GPIO_ATTR_ACTIVE_LOW,
                GPIO_NAME_WRITE_PROTECT: GPIO_ATTR_ACTIVE_HIGH,
            }

    def read(self, name):
        '''Reads an integer value from GPIO.

        Parameters:
            name: the name of GPIO property to read.

        Returns: current value (as integer), or raise I/O exceptions.
        '''
        assert self._gpio_root, "GPIO: not initialized."
        gpio_path = os.path.join(self._gpio_root, name)
        assert gpio_path, "GPIO: unknown property: %s" % name
        with open(gpio_path) as f:
            raw_value = int(f.read())

        # For newer version of OS, *.attr provides the polarity information of
        # GPIO pins.  We use polarity = 1 (active high) as default value.
        attr_path = gpio_path + '.attr'
        attr = GPIO_ATTR_ACTIVE_HIGH
        if name in self._override_attributes:
            attr = self._override_attributes[name]
        elif os.path.exists(attr_path):
            with open(attr_path) as f:
                attr = int(f.read())

        value = raw_value
        # attributes: bit 0 = polarity (active high=1/low=0)
        if (attr & GPIO_ATTR_ACTIVE_MASK) == GPIO_ATTR_ACTIVE_LOW:
            value = int(not raw_value)
        return value


def main():
    gpio = Gpio()
    try:
        gpio.setup()
        print ("developer switch status: %s" %
               sys.read(GPIO_NAME_DEVELOPER_SWITCH))
    except:
        print "GPIO failed."
        sys.exit(1)

if __name__ == '__main__':
    main()
