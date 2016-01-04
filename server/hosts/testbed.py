# Copyright 2015 The Chromium OS Authors. All rights reserved.
# Use of this source code is governed by a BSD-style license that can be
# found in the LICENSE file.

"""This class defines the TestBed class."""

import logging

import common

from autotest_lib.server.cros.dynamic_suite import constants
from autotest_lib.server.cros.dynamic_suite import frontend_wrappers
from autotest_lib.server.hosts import adb_host
from autotest_lib.server.hosts import teststation_host


class TestBed(object):
    """This class represents a collection of connected teststations and duts."""


    def __init__(self, hostname='localhost', host_attributes={},
                 adb_serials=None, **dargs):
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
        self.is_client_install_supported = False
        serials_from_attributes = host_attributes.get('serials')
        if serials_from_attributes:
            serials_from_attributes = serials_from_attributes.split(',')

        self.adb_device_serials = (adb_serials or
                                   serials_from_attributes or
                                   self.query_adb_device_serials())
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
            serials.extend(serial_attr.value.split(','))

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
        device_list.extend(self.adb_devices.values())
        return device_list


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


    def get_labels(self):
        """Return a list of the labels gathered from the devices connected.

        @return: A list of strings that denote the labels from all the devices
                 connected.
        """
        labels = []
        for adb_device in self.get_adb_devices().values():
            labels.extend(adb_device.get_labels())
        # Currently the board label will need to be modified for each adb
        # device.  We'll get something like 'board:android-shamu' and
        # we'll need to update it to 'board:android-shamu-1'.  Let's store all
        # the labels in a dict and keep track of how many times we encounter
        # it, that way we know what number to append.
        board_label_dict = {}
        updated_labels = []
        for label in labels:
            # Update the board labels
            if label.startswith(constants.BOARD_PREFIX):
                # Now let's grab the board num and append it to the board_label.
                board_num = board_label_dict.setdefault(label, 0) + 1
                board_label_dict[label] = board_num
                updated_labels.append('%s-%d' % (label, board_num))
            else:
                # We don't need to mess with this.
                updated_labels.append(label)
        return updated_labels


    def get_platform(self):
        """Return the platform of the devices.

        @return: A string representing the testbed platform.
        """
        return 'testbed'


    def repair(self):
        """Run through repair on all the devices."""
        for adb_device in self.get_adb_devices().values():
            adb_device.repair()


    def verify(self):
        """Run through verify on all the devices."""
        for device in self.get_all_hosts():
            device.verify()


    def cleanup(self):
        """Run through cleanup on all the devices."""
        for adb_device in self.get_adb_devices().values():
            adb_device.cleanup()

