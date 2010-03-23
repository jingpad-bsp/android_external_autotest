import logging, re, utils, dbus
from autotest_lib.client.bin import test
from autotest_lib.client.common_lib import error

class platform_DiskIterate(test.test):
    version = 1

    def run_once(self):

    	bus = dbus.SystemBus()

	proxy = bus.get_object("org.freedesktop.DeviceKit.Disks",
                               "/org/freedesktop/DeviceKit/Disks")

	foo = dbus.Interface(proxy, "org.freedesktop.DeviceKit.Disks")

	arrayiter = foo.EnumerateDevices()

	if not len(arrayiter):
	   raise error.TestFail('Unable to find at least one disk')
