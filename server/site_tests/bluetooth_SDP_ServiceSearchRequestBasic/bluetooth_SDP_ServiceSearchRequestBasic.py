# Copyright (c) 2013 The Chromium OS Authors. All rights reserved.
# Use of this source code is governed by a BSD-style license that can be
# found in the LICENSE file.

from autotest_lib.client.common_lib import error
from autotest_lib.server.cros.bluetooth import bluetooth_test


class bluetooth_SDP_ServiceSearchRequestBasic(bluetooth_test.BluetoothTest):
    """
    Verify the correct behaviour of the device when searching for services.
    """
    version = 1

    SDP_SERVER_CLASS_ID = 0x1000


    def correct_request(self):
        """Search the existing service on the DUT using the Tester.

        @return True if found, False if not found

        """
        # connect to the DUT via L2CAP using SDP socket
        self.tester.connect(self.adapter['Address'])
        # at least the SDP server service exists
        for size in 16, 32, 128:
            resp = self.tester.service_search_request(
                   [self.SDP_SERVER_CLASS_ID], 3, size)
            if not 0 in resp:
                return False
        return True


    def run_once(self):
        # Reset the adapter to the powered on, discoverable state.
        if not (self.device.reset_on() and
                self.device.set_discoverable(True)):
            raise error.TestFail('DUT could not be reset to initial state')

        self.adapter = self.device.get_adapter_properties()

        # Setup the tester as a generic computer.
        if not self.tester.setup('computer'):
            raise error.TestFail('Tester could not be initialized')

        # Since radio is involved, this test is not 100% reliable; instead we
        # repeat a few times until it succeeds.
        for failed_attempts in range(0, 5):
            if self.correct_request():
                break
        else:
            raise error.TestFail('Expected device was not found')

        # Record how many attempts this took, hopefully we'll one day figure out
        # a way to reduce this to zero and then the loop above can go away.
        self.write_perf_keyval({'failed_attempts': failed_attempts })
