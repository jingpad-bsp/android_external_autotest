# Copyright (c) 2013 The Chromium Authors. All rights reserved.
# Use of this source code is governed by a BSD-style license that can be
# found in the LICENSE file.

import collections
import logging
import os

from autotest_lib.client.bin import test
from autotest_lib.client.bin import utils
from autotest_lib.client.common_lib import error


class network_WlanDriver(test.test):
    """
    Ensure wireless devices have the expected associated kernel driver.
    """
    version = 1
    DEVICES = [ 'wlan0', 'mlan0' ]
    DEVICE_INFO_ROOT = '/sys/class/net'
    DeviceInfo = collections.namedtuple('DeviceInfo', ['vendor', 'device'])
    DEVICE_NAME_LOOKUP = {
        DeviceInfo('0x02df', '0x9129'): 'Marvell 88W8797 SDIO',
        DeviceInfo('0x168c', '0x002a'): 'Atheros AR9280',
        DeviceInfo('0x168c', '0x0030'): 'Atheros AR9382',
        DeviceInfo('0x168c', '0x0034'): 'Atheros AR9462',
        DeviceInfo('0x11ab', '0x2b38'): 'Marvell 88W8897 PCIE'
    }
    EXPECTED_DRIVER = {
            'Atheros AR9280': {
                    '3.4': 'kernel/drivers/net/wireless/ath/ath9k/ath9k.ko',
                    '3.8': 'kernel/drivers/net/wireless-3.4/ath/ath9k/ath9k.ko'
            },
            'Atheros AR9382': {
                    '3.4': 'kernel/drivers/net/wireless/ath/ath9k/ath9k.ko',
                    '3.8': 'kernel/drivers/net/wireless-3.4/ath/ath9k/ath9k.ko'
            },
            'Atheros AR9462': {
                    '3.4': 'kernel/drivers/net/wireless/ath/ath9k_btcoex/'
                           'ath9k_btcoex.ko',
                    '3.8': 'kernel/drivers/net/wireless-3.4/ath/ath9k_btcoex/'
                           'ath9k_btcoex.ko'
            },
            'Marvell 88W8797 SDIO': {
                    '3.4': 'kernel/drivers/net/wireless/mwifiex/'
                           'mwifiex_sdio.ko',
                    '3.8': 'kernel/drivers/net/wireless-3.4/mwifiex/'
                           'mwifiex_sdio.ko'
            },
            'Marvell 88W8897 PCIE': {
                     '3.8': 'kernel/drivers/net/wireless/mwifiex/'
                            'mwifiex_sdio.ko'
            }
    }


    def get_kernel_base(self):
        """
        Get the base kernel revision for a device under test.

        @return string representing the kernel base revision, e.g. "3.4".

        """
        release = utils.system_output('uname -r')
        return '.'.join(release.split('.')[:2])


    def get_net_device_info(self, device_name):
        """
        Get the information associated with a device.

        @param device_name string name of device to get information on.
        @return list representing the identifying device information, namely
            [ 'part_name', 'module_path' ], or None if the device does not
            exist.

        """
        device_path = os.path.join(self.DEVICE_INFO_ROOT, device_name,
                                     'device')
        if not os.path.exists(device_path):
            return None
        with open(os.path.join(device_path, 'vendor'), 'r') as f:
            vendor_id = f.read().rstrip()
        with open(os.path.join(device_path, 'device'), 'r') as f:
            product_id = f.read().rstrip()

        driver_info = self.DeviceInfo(vendor_id, product_id)
        if not driver_info in self.DEVICE_NAME_LOOKUP:
            raise error.TestNAError('Device vendor/product pair %r '
                                    'for device %s is unknown!' %
                                    (driver_info, device_name))
        device_name = self.DEVICE_NAME_LOOKUP[driver_info]
        logging.info('Device is %s',  device_name)

        module_name = os.path.basename(os.readlink(os.path.join(
                device_path, 'driver', 'module')))
        module_path = utils.system_output('modprobe -l %s' % module_name)
        return (device_name, module_path)


    def run_once(self):
        """Test main loop"""
        base_revision = self.get_kernel_base()
        logging.info('Kernel base is %s', base_revision)

        found_devices = 0
        for device in self.DEVICES:
            devinfo = self.get_net_device_info(device)

            if not devinfo:
                continue

            device_name, module_path = devinfo
            logging.info('Device name %s, module path %s',
                         device_name, module_path)
            if not device_name in self.EXPECTED_DRIVER:
                raise error.TestNAError('Unexpected device name %s' %
                                        device_name)

            if not base_revision in self.EXPECTED_DRIVER[device_name]:
                raise error.TestNAError('Unexpected base kernel revision %s '
                                        'with device name %s' %
                                        (base_revision, device_name))

            expected_driver = self.EXPECTED_DRIVER[device_name][base_revision]
            if module_path != expected_driver:
                raise error.TestFail('Unexpected driver for %s/%s; '
                                     'got %s but expected %s' %
                                     (base_revision, device_name,
                                      module_path, expected_driver))
            found_devices += 1
        if not found_devices:
            raise error.TestNAError('Found no wireless devices?')
