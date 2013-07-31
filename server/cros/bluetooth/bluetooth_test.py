# Copyright (c) 2013 The Chromium OS Authors. All rights reserved.
# Use of this source code is governed by a BSD-style license that can be
# found in the LICENSE file.

from autotest_lib.server import test
from autotest_lib.server.cros import interactive_client
from autotest_lib.server.cros.bluetooth import bluetooth_client
from autotest_lib.server.cros.bluetooth import bluetooth_tester


class BluetoothTest(test.test):
    """Base class for Bluetooth tests.

    BluetoothTest provides a common warmup() and cleanup() function for the
    collection of Bluetooth tests that sets the following properties, depending
    on the arguments to the test and properties of the test object:

      self.client - BluetoothClient object for the device being tested
      self.tester - BluetoothTester object for the device's partner tester
      self.interactive - InteractiveClient object for the device

    The latter two may be None if the test is initialized from the control file
    with the tester_host parameter as None and/or the interactive argument as
    False.

    It is not mandatory to use this base class for Bluetooth tests, it is for
    convenience only. A test with special requirements, or a need to derive
    from a different base class, may instantiate and clean-up the associated
    objects on its own.

    """

    def warmup(self, client_host, tester_host, interactive=False):
        """Initialize the test member objects based on its arguments."""
        super(BluetoothTest, self).warmup()

        self.client = bluetooth_client.BluetoothClient(client_host)

        if tester_host:
            self.tester = bluetooth_tester.BluetoothTester(tester_host)
        else:
            self.tester = None

        if interactive:
            self.interactive = interactive_client.InteractiveClient(client_host)
        else:
            self.interactive = None


    def cleanup(self):
        """Close the test member objects."""
        if self.interactive:
            self.interactive.close()
        self.client.close()
        if self.tester:
            self.tester.close()

        super(BluetoothTest, self).cleanup()
