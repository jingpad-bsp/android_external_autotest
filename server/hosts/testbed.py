# Copyright 2015 The Chromium OS Authors. All rights reserved.
# Use of this source code is governed by a BSD-style license that can be
# found in the LICENSE file.

"""This class defines the TestBed class."""

import logging

import common

from autotest_lib.server.cros.dynamic_suite import frontend_wrappers
from autotest_lib.server.hosts import adb_host
from autotest_lib.server.hosts import teststation_host


class TestBed(object):
    """This class represents a collection of connected teststations and duts."""


    def __init__(self, hostname='localhost', adb_serials=None):
        """Initialize a TestBed.

        This will create the Test Station Host and connected hosts (ADBHost for
        now) and allow the user to retrieve them.

        @param hostname: Hostname of the test station connected to the duts.
        @param serials: List of adb device serials.
        """
        logging.info('Initializing TestBed centered on host: %s', hostname)
        self.hostname = hostname
        self.teststation = teststation_host.create_teststationhost(
                hostname=hostname)
        self.adb_device_serials = adb_serials or self.query_adb_device_serials()
        self.adb_devices = {}
        for adb_serial in self.adb_device_serials:
            self.adb_devices[adb_serial] = adb_host.ADBHost(
                hostname=hostname, teststation=self.teststation,
                adb_serial=adb_serial)


    def query_adb_device_serials(self):
        """Get a list of devices currently attached to the test station.

        @returns a list of adb devices.
        """
        serials = []
        # Let's see if we can get the serials via host attributes.
        afe = frontend_wrappers.RetryingAFE(timeout_min=5, delay_sec=10)
        serials_attr = afe.get_host_attribute('serials', hostname=self.hostname)
        for serial_attr in serials_attr:
            serials.append(serial_attr.value)

        # Looks like we got nothing from afe, let's probe the test station.
        if not serials:
            # TODO(kevcheng): Refactor teststation to be a class and make the
            # ADBHost adb_devices a static method I can use here.  For now this
            # is pretty much a c/p of the _adb_devices() method from ADBHost.
            serials = adb_host.ADBHost.parse_device_serials(
                self.teststation.run('adb devices').stdout)

        return serials


    def get_all_hosts(self):
        """Return a list of all the hosts in this testbed.

        @return: List of the hosts which includes the test station and the adb
                 devices.
        """
        device_list = [self.teststation]
        return device_list.extend(self.adb_devices.values())


    def get_test_station(self):
        """Return the test station host object.

        @return: The test station host object.
        """
        return self.teststation


    def get_adb_devices(self):
        """Return the adb host objects.

        @return: A dict of adb device serials to their host objects.
        """
        return self.adb_devices
