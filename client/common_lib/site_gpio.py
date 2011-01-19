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
            return int(f.read())


def main():
    gpio = Gpio()
    try:
        gpio.setup()
        print "developer switch status: %s" % sys.read('developer_switch')
    except:
        print "GPIO failed."
        sys.exit(1)

if __name__ == '__main__':
    main()
