# Copyright (c) 2011 The Chromium OS Authors. All rights reserved.
# Use of this source code is governed by a BSD-style license that can be
# found in the LICENSE file.

from autotest_lib.client.bin import test, utils
from autotest_lib.client.common_lib import error

import dbus

class platform_CrosDisksDBus(test.test):
    version = 1

    def validate_disk_properties(self, disk):
        # Disk properties provided by the API
        disk_properties = (
            ('DeviceFile', dbus.String),
            ('DeviceIsDrive', dbus.Boolean),
            ('DeviceIsMediaAvailable', dbus.Boolean),
            ('DeviceIsMounted', dbus.Boolean),
            ('DeviceIsOpticalDisc', dbus.Boolean),
            ('DeviceIsReadOnly', dbus.Boolean),
            ('DeviceMountPaths', dbus.Array),
            ('DevicePresentationHide', dbus.Boolean),
            ('DeviceSize', dbus.UInt64),
            ('DriveIsRotational', dbus.Boolean),
            ('DriveModel', dbus.String),
            ('IdLabel', dbus.String),
            ('NativePath', dbus.String),
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

    def test_is_alive(self):
        # Check if CrosDisks server is alive.
        is_alive = self.cros_disks.IsAlive()
        if not is_alive:
            raise error.TestFail("Unable to talk to the disk daemon")

    def test_enumerate_device_files(self):
        # Check if EnumerateDeviceFiles method returns a list of devices.
        devices = self.cros_disks.EnumerateDeviceFiles()
        for device in devices:
            if not device or not isinstance(device, dbus.String):
                raise error.TestFail(
                        "device returned by EnumerateDeviceFiles "
                        "should be a non-empty string")

    def test_get_device_properties(self):
        # Check if GetDeviceProperties method returns valid properties.
        devices = self.cros_disks.EnumerateDeviceFiles()
        for device in devices:
            properties = self.cros_disks.GetDeviceProperties(device)
            self.validate_disk_properties(properties)

    def test_get_device_properties_of_nonexistent_device(self):
        try:
            properties = self.cros_disks.GetDeviceProperties('/nonexistent')
        except dbus.DBusException:
            return
        raise error.TestFail(
            "GetDeviceProperties of a nonexistent device should fail")

    def test_mount_nonexistent_device(self):
        try:
            path = self.cros_disks.FilesystemMount('/nonexistent', '', [])
        except dbus.DBusException:
            return
        raise error.TestFail("Mounting a nonexistent device should fail")

    def test_unmount_nonexistent_device(self):
        try:
            self.cros_disks.FilesystemUnmount('/nonexistent', [])
        except dbus.DBusException:
            return
        raise error.TestFail("Unmounting a nonexistent device should fail")

    def run_once(self):
        bus = dbus.SystemBus()
        proxy = bus.get_object('org.chromium.CrosDisks',
                               '/org/chromium/CrosDisks')
        self.cros_disks = dbus.Interface(proxy, 'org.chromium.CrosDisks')
        self.test_is_alive()
        self.test_enumerate_device_files()
        self.test_get_device_properties()
        self.test_get_device_properties_of_nonexistent_device()
        self.test_mount_nonexistent_device()
        self.test_unmount_nonexistent_device()
