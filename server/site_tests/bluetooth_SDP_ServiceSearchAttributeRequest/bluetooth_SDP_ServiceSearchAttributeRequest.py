# Copyright (c) 2013 The Chromium OS Authors. All rights reserved.
# Use of this source code is governed by a BSD-style license that can be
# found in the LICENSE file.

from autotest_lib.client.common_lib import error
from autotest_lib.server.cros.bluetooth import bluetooth_test

class bluetooth_SDP_ServiceSearchAttributeRequest(bluetooth_test.BluetoothTest):
    """
    Verify the correct behaviour of the device when searching for services and
    attributes.
    """
    version = 1

    MAX_ATTR_BYTE_CNT             = 300

    NON_EXISTING_SERVICE_CLASS_ID = 0x9875
    SDP_SERVER_CLASS_ID           = 0x1000
    PUBLIC_BROWSE_GROUP_CLASS_ID  = 0x1002

    NON_EXISTING_ATTRIBUTE_ID     = 0xABCD
    SERVICE_CLASS_ID_ATTRIBUTE_ID = 0x0001


    def test_non_existing(self, class_id, attr_id):
        """Check that a single attribute of a single service does not exist

        @param class_id: Class ID of service to check.
        @param attr_id: ID of attribute to check.

        @return True if service or attribute does not exist, False otherwise

        """
        for size in 16, 32, 128:
            result = self.tester.service_search_attribute_request(
                         [class_id],
                         self.MAX_ATTR_BYTE_CNT,
                         [attr_id],
                         size)
            if result != []:
                return False

        return True


    def test_non_existing_service(self):
        """Implementation of test TP/SERVER/SSA/BV-01-C from SDP Specification.

        @return True if test passes, False if test fails

        """
        return self.test_non_existing(self.NON_EXISTING_SERVICE_CLASS_ID,
                                      self.SERVICE_CLASS_ID_ATTRIBUTE_ID)


    def test_non_existing_attribute(self):
        """Implementation of test TP/SERVER/SSA/BV-02-C from SDP Specification.

        @return True if test passes, False if test fails

        """
        return self.test_non_existing(self.PUBLIC_BROWSE_GROUP_CLASS_ID,
                                      self.NON_EXISTING_ATTRIBUTE_ID)


    def test_non_existing_service_attribute(self):
        """Implementation of test TP/SERVER/SSA/BV-03-C from SDP Specification.

        @return True if test passes, False if test fails

        """
        return self.test_non_existing(self.NON_EXISTING_SERVICE_CLASS_ID,
                                      self.NON_EXISTING_ATTRIBUTE_ID)


    def test_existing_service_attribute(self):
        """Implementation of test TP/SERVER/SSA/BV-04-C from SDP Specification.

        @return True if test passes, False if test fails

        """
        for size in 16, 32, 128:
            result = self.tester.service_search_attribute_request(
                         [self.SDP_SERVER_CLASS_ID],
                         self.MAX_ATTR_BYTE_CNT,
                         [self.SERVICE_CLASS_ID_ATTRIBUTE_ID],
                         size)
            if result != [[self.SERVICE_CLASS_ID_ATTRIBUTE_ID,
                           [self.SDP_SERVER_CLASS_ID]]]:
                return False

        return True


    def correct_request(self):
        """Run tests for Service Search Attribute request.

        @return True if all tests finishes correctly, False otherwise

        """
        # connect to the DUT via L2CAP using SDP socket
        self.tester.connect(self.adapter['Address'])

        return (self.test_non_existing_service() and
                self.test_non_existing_attribute() and
                self.test_non_existing_service_attribute() and
                self.test_existing_service_attribute())


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
            raise error.TestFail('Expected services/attributes were not found')

        # Record how many attempts this took, hopefully we'll one day figure out
        # a way to reduce this to zero and then the loop above can go away.
        self.write_perf_keyval({'failed_attempts': failed_attempts })
