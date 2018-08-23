# Copyright (c) 2011 The Chromium OS Authors. All rights reserved.
# Use of this source code is governed by a BSD-style license that can be
# found in the LICENSE file.

import dbus

from autotest_lib.client.bin import test
from autotest_lib.client.common_lib import error
from autotest_lib.client.cros.cros_disks import CrosDisksTester

class CrosDisksAPITester(CrosDisksTester):

    # See MountErrorType defined in system_api/dbus/cros-disks/dbus-constants.h
    MOUNT_ERROR_PATH_NOT_MOUNTED = 6
    MOUNT_ERROR_INVALID_DEVICE_PATH = 100

    def __init__(self, test):
        super(CrosDisksAPITester, self).__init__(test)

    def get_tests(self):
        return [
            self.test_enumerate_devices,
            self.test_get_device_properties,
            self.test_get_device_properties_of_nonexistent_device,
            self.test_mount_nonexistent_device,
            self.test_mount_boot_device_rejected,
            self.test_unmount_nonexistent_device,
        ]

    def validate_disk_properties(self, disk):
        # Disk properties provided by the API
        disk_properties = (
            ('DeviceFile', dbus.String),
            ('DeviceIsDrive', dbus.Boolean),
            ('DeviceIsMediaAvailable', dbus.Boolean),
            ('DeviceIsOnBootDevice', dbus.Boolean),
            ('DeviceIsVirtual', dbus.Boolean),
            ('DeviceIsMounted', dbus.Boolean),
            ('DeviceIsReadOnly', dbus.Boolean),
            ('DeviceMediaType', dbus.UInt32),
            ('DeviceMountPaths', dbus.Array),
            ('DevicePresentationHide', dbus.Boolean),
            ('DeviceSize', dbus.UInt64),
            ('DriveModel', dbus.String),
            ('IdLabel', dbus.String),
            ('NativePath', dbus.String),
            ('FileSystemType', dbus.String),
        )

        for (prop_name, prop_value_type) in disk_properties:
            # Check if all disk properties are set.
            if prop_name not in disk:
                raise error.TestFail("disk.%s not found" % prop_name)

            # Check if each disk property has the right data type.
            prop_value = disk[prop_name]
            if not isinstance(prop_value, prop_value_type):
                raise error.TestFail(
                        "disk.%s is %s, but %s expected"
                        % (prop_name, type(prop_value), prop_value_type))

        # Check if DeviceFile has a proper value.
        if not disk['DeviceFile']:
            raise error.TestFail(
                    "disk.DeviceFile should not be empty")

        # Check if the values of DeviceIsMounted and DeviceMountPaths
        # are consistent.
        mount_paths = disk['DeviceMountPaths']
        if disk['DeviceIsMounted']:
            if len(mount_paths) == 0:
                raise error.TestFail(
                        "disk.DeviceMountPaths should not be empty "
                        "if disk.DeviceIsMounted is true")
        else:
            if len(mount_paths) != 0:
                raise error.TestFail(
                        "disk.DeviceMountPaths should be empty "
                        "if disk.DeviceIsMounted is false")

        if mount_paths.signature != dbus.Signature('s'):
            raise error.TestFail(
                    "disk.DeviceMountPaths should contain only strings")

        for mount_path in mount_paths:
            if not mount_path:
                raise error.TestFail(
                        "disk.DeviceMountPaths should not contain any "
                        "empty string")

    def test_enumerate_devices(self):
        # Check if EnumerateDevices method returns a list of devices.
        devices = self.cros_disks.enumerate_devices()
        for device in devices:
            if not device or not isinstance(device, dbus.String):
                raise error.TestFail(
                        "device returned by EnumerateDevices "
                        "should be a non-empty string")

    def test_get_device_properties(self):
        # Check if GetDeviceProperties method returns valid properties.
        devices = self.cros_disks.enumerate_devices()
        for device in devices:
            properties = self.cros_disks.get_device_properties(device)
            self.validate_disk_properties(properties)

    def test_get_device_properties_of_nonexistent_device(self):
        try:
            properties = self.cros_disks.get_device_properties('/nonexistent')
        except dbus.DBusException:
            return
        raise error.TestFail(
            "GetDeviceProperties of a nonexistent device should fail")

    def test_mount_nonexistent_device(self):
        self.cros_disks.mount('/dev/nonexistent', '', [])
        self.cros_disks.expect_mount_completion({
            'source_path': '/dev/nonexistent',
            'mount_path':  '',
        })

    def test_mount_boot_device_rejected(self):
        # Check if EnumerateDevices method returns a list of devices.
        devices = self.cros_disks.enumerate_devices()
        for device in devices:
            properties = self.cros_disks.get_device_properties(device)
            self.validate_disk_properties(properties)
            if not properties['DeviceIsOnBootDevice']:
                continue

            self.cros_disks.mount(device, '', [])
            self.cros_disks.expect_mount_completion({
                'source_path': device,
                'mount_path': '',
                'status': self.MOUNT_ERROR_INVALID_DEVICE_PATH
            })

    def test_unmount_nonexistent_device(self):
        status = self.cros_disks.unmount('/dev/nonexistent', [])
        if status != self.MOUNT_ERROR_PATH_NOT_MOUNTED:
            raise error.TestFail("Unexpected unmount error code %d" % status)


class platform_CrosDisksDBus(test.test):
    version = 1

    def run_once(self, *args, **kwargs):
        tester = CrosDisksAPITester(self)
        tester.run(*args, **kwargs)
