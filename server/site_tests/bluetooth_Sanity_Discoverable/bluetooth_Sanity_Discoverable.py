# Copyright (c) 2013 The Chromium OS Authors. All rights reserved.
# Use of this source code is governed by a BSD-style license that can be
# found in the LICENSE file.

import cgi
import logging

from autotest_lib.client.common_lib import error
from autotest_lib.client.common_lib.cros.bluetooth import bluetooth_socket
from autotest_lib.server.cros.bluetooth import bluetooth_test


class bluetooth_Sanity_Discoverable(bluetooth_test.BluetoothTest):
    """
    Verify that the client is discoverable from the tester.
    """
    version = 1


    def run_once(self):
        # Reset the adapter to the powered on, discoverable state.
        if not (self.client.reset_on() and
                self.client.set_discoverable(True)):
            raise error.TestFail('DUT could not be reset to initial state')

        self.adapter = self.client.get_adapter_properties()

        if self.interactive:
            self.interactive.login()
            self.interactive.append_output(
                    '<p>The DUT is in the discoverable state. '
                    '<p>Please verify that you can discover the device ' +
                    ('<b>%s</b> with address <b>%s</b> from the tester.' %
                     (cgi.escape(self.adapter['Alias']),
                      cgi.escape(self.adapter['Address']))))

        if self.tester:
            # Setup the tester as a generic computer.
            if not self.tester.setup('computer'):
                raise error.TestFail('Tester could not be initialized')
            # Discover devices from the tester.
            devices = self.tester.discover_devices()
            if devices == False:
                raise error.TestFail('Tester could not discover devices')
            # Iterate the devices we received in the discovery phase and
            # look for the DUT.
            for address, address_type, rssi, flags, eirdata in devices:
                if address == self.adapter['Address']:
                    logging.info('Found device with RSSI %d', rssi)
                    eir = bluetooth_socket.parse_eir(eirdata)
                    try:
                        eir_name = eir[bluetooth_socket.EIR_NAME_COMPLETE]
                        if eir_name != self.adapter['Alias']:
                            raise error.TestFail(
                                    'Device did not have expected name ' +
                                    '"%s" != "%s"' % (eir_name,
                                                      self.adapter['Alias']))
                    except KeyError:
                        raise error.TestFail('Found device did not have a name')
                    # Break out of the loop to skip the failure condition and
                    # pass the test.
                    break
            else:
                raise error.TestFail('Expected device was not found')

        if self.interactive:
            self.interactive.append_buttons('Device Found', 'Device Not Found')
            result = self.interactive.wait_for_button(timeout=600)
            if result != 0:
                raise error.TestFail('User indicated test failed')
