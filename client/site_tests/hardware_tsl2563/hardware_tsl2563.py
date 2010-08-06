# Copyright (c) 2010 The Chromium OS Authors. All rights reserved.
# Use of this source code is governed by a BSD-style license that can be
# found in the LICENSE file.

import logging, os
from autotest_lib.client.bin import test, utils
from autotest_lib.client.common_lib import error


class hardware_tsl2563(test.test):
    """
    Test the TSL2560/1/2/3 Light Sensor device.
    Failure to find the device likely indicates the kernel module is not loaded.
    Or it could mean the I2C probe for the device failed because of an incorrect
    I2C address or bus specification.
    The upscript /etc/init/powerd.conf should properly load the driver so that
    we can find its files in /sys/class/iio/device0/.
    """
    version = 1

    def run_once(self):
        try:
            lux_out = utils.read_one_line('/sys/class/iio/device0/lux')
        except:
            raise error.TestFail('The tsl2563 driver is not '
                                 'exporting its lux file')
        lux = int(lux_out)
        if lux < 0:
            raise error.TestFail('Invalid tsl2563 lux string (%s)' % lux_out)
        logging.debug("tsl2563 lux value is %d", lux)

