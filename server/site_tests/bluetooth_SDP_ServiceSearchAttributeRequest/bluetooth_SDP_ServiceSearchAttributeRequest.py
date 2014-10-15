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

    MAX_ATTR_BYTE_CNT                = 300

    NON_EXISTING_SERVICE_CLASS_ID    = 0x9875
    SDP_SERVER_CLASS_ID              = 0x1000
    PUBLIC_BROWSE_GROUP_CLASS_ID     = 0x1002
    GAP_CLASS_ID                     = 0x1800
    PNP_INFORMATION_CLASS_ID         = 0x1200
    PUBLIC_BROWSE_ROOT               = 0x1002
    AVRCP_TG_CLASS_ID                = 0x110C

    NON_EXISTING_ATTRIBUTE_ID        = 0xABCD
    SERVICE_CLASS_ID_ATTRIBUTE_ID    = 0x0001
    SERVICE_DATABASE_STATE_ATTR_ID   = 0x0201
    PROTOCOL_DESCRIPTOR_LIST_ATTR_ID = 0x0004
    ICON_URL_ATTR_ID                 = 0x000C
    VERSION_NUMBER_LIST_ATTR_ID      = 0x0200
    PROFILE_DESCRIPTOR_LIST_ATTR_ID  = 0x0009
    BROWSE_GROUP_LIST_ATTR_ID        = 0x0005
    DOCUMENTATION_URL_ATTR_ID        = 0x000A
    CLIENT_EXECUTABLE_URL_ATTR_ID    = 0x000B
    ADDITIONAL_PROTOCOLLIST_ATTR_ID  = 0x000D

    L2CAP_UUID                       = 0x0100
    ATT_UUID                         = 0x0007

    BLUEZ_URL                        = 'http://www.bluez.org/'

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


    def get_attribute(self, class_id, attr_id, size):
        """Get a single attribute of a single service using Service Search
        Attribute Request.

        @param class_id: Class ID of service to check.
        @param attr_id: ID of attribute to check.
        @param size: Preferred size of UUID.

        @return attribute value if attribute exists, None otherwise

        """
        res = self.tester.service_search_attribute_request(
                  [class_id], self.MAX_ATTR_BYTE_CNT, [attr_id], size)

        if (isinstance(res, list) and len(res) == 1 and
            isinstance(res[0], list) and len(res[0]) == 2 and
            res[0][0] == attr_id):
            return res[0][1]

        return None


    def test_attribute(self, class_id, attr_id):
        """Test a single attribute of a single service using 16-bit, 32-bit and
        128-bit size of UUID.

        @param class_id: Class ID of service to check.
        @param attr_id: ID of attribute to check.

        @return attribute value if attribute exists and values from three tests
        are equal, None otherwise

        """
        result_16 = self.get_attribute(class_id, attr_id, 16)
        for size in 32, 128:
            result_cur = self.get_attribute(class_id, attr_id, size)
            if result_16 != result_cur:
                return None

        return result_16


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
        value = self.test_attribute(self.SDP_SERVER_CLASS_ID,
                                    self.SERVICE_CLASS_ID_ATTRIBUTE_ID)
        return value == [self.SDP_SERVER_CLASS_ID]


    def test_service_database_state_attribute(self):
        """Implementation of test TP/SERVER/SSA/BV-08-C from SDP Specification.

        @return True if test passes, False if test fails

        """
        value = self.test_attribute(self.SDP_SERVER_CLASS_ID,
                                    self.SERVICE_DATABASE_STATE_ATTR_ID)
        return isinstance(value, int)


    def test_protocol_descriptor_list_attribute(self):
        """Implementation of test TP/SERVER/SSA/BV-11-C from SDP Specification.

        @return True if test passes, False if test fails

        """
        value = self.test_attribute(self.GAP_CLASS_ID,
                                    self.PROTOCOL_DESCRIPTOR_LIST_ATTR_ID)
        return value == [[self.L2CAP_UUID, 31], [self.ATT_UUID, 1, 8]]


    def test_browse_group_attribute(self):
        """Implementation of test TP/SERVER/SSA/BV-12-C from SDP Specification.

        @return True if test passes, False if test fails

        """
        value = self.test_attribute(self.GAP_CLASS_ID,
                                    self.BROWSE_GROUP_LIST_ATTR_ID)
        return value == [self.PUBLIC_BROWSE_ROOT]


    def test_icon_url_attribute(self):
        """Implementation of test TP/SERVER/SSA/BV-15-C from SDP Specification.

        @return True if test passes, False if test fails

        """
        value = self.test_attribute(self.GAP_CLASS_ID,
                                    self.ICON_URL_ATTR_ID)
        return value == self.BLUEZ_URL


    def test_version_list_attribute(self):
        """Implementation of test TP/SERVER/SSA/BV-19-C from SDP Specification.

        @return True if test passes, False if test fails

        """
        value = self.test_attribute(self.SDP_SERVER_CLASS_ID,
                                    self.VERSION_NUMBER_LIST_ATTR_ID)
        return isinstance(value, list) and value != []


    def test_profile_descriptor_list_attribute(self):
        """Implementation of test TP/SERVER/SSA/BV-20-C from SDP Specification.

        @return True if test passes, False if test fails

        """
        value = self.test_attribute(self.PNP_INFORMATION_CLASS_ID,
                                    self.PROFILE_DESCRIPTOR_LIST_ATTR_ID)
        return (isinstance(value, list) and len(value) == 1 and
                isinstance(value[0], list) and len(value[0]) == 2 and
                value[0][0] == self.PNP_INFORMATION_CLASS_ID)


    def test_documentation_url_attribute(self):
        """Implementation of test TP/SERVER/SSA/BV-21-C from SDP Specification.

        @return True if test passes, False if test fails

        """
        value = self.test_attribute(self.GAP_CLASS_ID,
                                    self.DOCUMENTATION_URL_ATTR_ID)
        return value == self.BLUEZ_URL


    def test_client_executable_url_attribute(self):
        """Implementation of test TP/SERVER/SSA/BV-22-C from SDP Specification.

        @return True if test passes, False if test fails

        """
        value = self.test_attribute(self.GAP_CLASS_ID,
                                    self.CLIENT_EXECUTABLE_URL_ATTR_ID)
        return value == self.BLUEZ_URL


    def test_additional_protocol_descriptor_list_attribute(self):
        """Implementation of test TP/SERVER/SSA/BV-23-C from SDP Specification.

        @return True if test passes, False if test fails

        """
        value = self.test_attribute(self.AVRCP_TG_CLASS_ID,
                                    self.ADDITIONAL_PROTOCOLLIST_ATTR_ID)
        return isinstance(value, list) and value != []


    def correct_request(self):
        """Run tests for Service Search Attribute request.

        @return True if all tests finishes correctly, False otherwise

        """
        # connect to the DUT via L2CAP using SDP socket
        self.tester.connect(self.adapter['Address'])

        return (self.test_non_existing_service() and
                self.test_non_existing_attribute() and
                self.test_non_existing_service_attribute() and
                self.test_existing_service_attribute() and
                self.test_service_database_state_attribute() and
                self.test_protocol_descriptor_list_attribute() and
                self.test_browse_group_attribute() and
                self.test_icon_url_attribute() and
                self.test_version_list_attribute() and
                self.test_profile_descriptor_list_attribute() and
                self.test_documentation_url_attribute() and
                self.test_client_executable_url_attribute() and
                self.test_additional_protocol_descriptor_list_attribute())


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
        self.write_perf_keyval({'failed_attempts': failed_attempts})
