# Copyright (c) 2013 The Chromium OS Authors. All rights reserved.
# Use of this source code is governed by a BSD-style license that can be
# found in the LICENSE file.

from autotest_lib.client.common_lib import error
from autotest_lib.server.cros.bluetooth import bluetooth_test
import uuid
import xml.etree.ElementTree as ET

class bluetooth_SDP_ServiceAttributeRequest(bluetooth_test.BluetoothTest):
    """
    Verify the correct behaviour of the device when searching for attributes of
    services.
    """
    version = 1

    MAX_REC_CNT                      = 3
    MAX_ATTR_BYTE_CNT                = 300

    SDP_SERVER_CLASS_ID              = 0x1000
    SERVICE_RECORD_HANDLE_ATTR_ID    = 0x0000

    GAP_CLASS_ID                     = 0x1800
    BROWSE_GROUP_LIST_ATTR_ID        = 0x0005
    PUBLIC_BROWSE_ROOT               = 0x1002

    BLUEZ_URL                        = 'http://www.bluez.org/'
    DOCUMENTATION_URL_ATTR_ID        = 0x000A
    CLIENT_EXECUTABLE_URL_ATTR_ID    = 0x000B
    ICON_URL_ATTR_ID                 = 0x000C

    PROTOCOL_DESCRIPTOR_LIST_ATTR_ID = 0x0004
    L2CAP_UUID                       = 0x0100
    ATT_UUID                         = 0x0007

    PNP_INFORMATION_CLASS_ID         = 0x1200
    MIN_ATTR_BYTE_CNT                = 7

    VERSION_NUMBER_LIST_ATTR_ID      = 0x0200
    SERVICE_DATABASE_STATE_ATTR_ID   = 0x0201

    AVRCP_TG_CLASS_ID                = 0x110c
    PROFILE_DESCRIPTOR_LIST_ATTR_ID  = 0x0009
    ADDITIONAL_PROTOCOLLIST_ATTR_ID  = 0x000D

    FAKE_SERVICE_PATH                = '/autotest/fake_service'
    FAKE_SERVICE_CLASS_ID            = 0xCDEF
    FAKE_ATTRIBUTE_VALUE             = 42
    LANGUAGE_BASE_ATTRIBUTE_ID       = 0x0006
    FAKE_GENERAL_ATTRIBUTE_IDS       = [
                                        0x0003, # TP/SERVER/SA/BV-04-C
                                        0x0002, # TP/SERVER/SA/BV-06-C
                                        0x0007, # TP/SERVER/SA/BV-07-C
                                        0x0008, # TP/SERVER/SA/BV-10-C
                                        # TP/SERVER/SA/BV-09-C:
                                        LANGUAGE_BASE_ATTRIBUTE_ID
                                       ]
    FAKE_LANGUAGE_ATTRIBUTE_OFFSETS  = [
                                        0x0000, # TP/SERVER/SA/BV-12-C
                                        0x0001, # TP/SERVER/SA/BV-13-C
                                        0x0002  # TP/SERVER/SA/BV-14-C
                                       ]
    NON_EXISTING_ATTRIBUTE_ID        = 0xFEDC
    BLUETOOTH_BASE_UUID              = 0x0000000000001000800000805F9B34FB
    SERVICE_CLASS_ID_ATTR_ID         = 0x0001

    ERROR_CODE_INVALID_RECORD_HANDLE = 0x0002
    ERROR_CODE_INVALID_SYNTAX        = 0x0003
    ERROR_CODE_INVALID_PDU_SIZE      = 0x0004
    INVALID_RECORD_HANDLE            = 0xFEEE
    INVALID_SYNTAX_REQUEST           = '123'
    INVALID_PDU_SIZE                 = 11


    def get_single_handle(self, class_id):
        """Send a Service Search Request to get a handle for specific class ID.

        @return -1 if request failed, record handle as int otherwise

        """
        res = self.tester.service_search_request([class_id], self.MAX_REC_CNT)
        if not (isinstance(res, list) and len(res) > 0):
            return -1
        return res[0]


    def test_record_handle_attribute(self):
        """Implementation of test TP/SERVER/SA/BV-01-C from SDP Specification.

        @return True if test passes, False if test fails

        """
        # Send Service Search Request to find out record handle for
        # SDP Server service.
        record_handle = self.get_single_handle(self.SDP_SERVER_CLASS_ID)
        if record_handle == -1:
            return False

        # Send Service Attribute Request for Service Record Handle Attribute.
        res = self.tester.service_attribute_request(
                  record_handle,
                  self.MAX_ATTR_BYTE_CNT,
                  [self.SERVICE_RECORD_HANDLE_ATTR_ID])

        # Ensure that returned attribute is correct.
        return res == [self.SERVICE_RECORD_HANDLE_ATTR_ID, record_handle]


    def get_attribute(self, class_id, attr_id):
        """Get a single attribute of a single service

        @param class_id: Class ID of service to check.
        @param attr_id: ID of attribute to check.

        @return attribute value if attribute exists, None otherwise

        """
        record_handle = self.get_single_handle(class_id)
        if record_handle == -1:
            return False

        res = self.tester.service_attribute_request(
                  record_handle, self.MAX_ATTR_BYTE_CNT, [attr_id])

        if isinstance(res, list) and len(res) == 2 and res[0] == attr_id:
            return res[1]
        return None


    def test_attribute(self, class_id, attr_id, attr_value):
        """Test a single attribute of a single service

        @param class_id: Class ID of service to check.
        @param attr_id: ID of attribute to check.
        @param attr_value: expected value of the attribute

        @return True if value of attribute equals to attr_value, False otherwise

        """
        record_handle = self.get_single_handle(class_id)
        if record_handle == -1:
            return False

        res = self.tester.service_attribute_request(
                  record_handle, self.MAX_ATTR_BYTE_CNT, [attr_id])

        return res == [attr_id, attr_value]


    def test_browse_group_attribute(self):
        """Implementation of test TP/SERVER/SA/BV-08-C from SDP Specification.

        @return True if test passes, False if test fails

        """
        return self.test_attribute(self.GAP_CLASS_ID,
                                   self.BROWSE_GROUP_LIST_ATTR_ID,
                                   [self.PUBLIC_BROWSE_ROOT])


    def test_icon_url_attribute(self):
        """Implementation of test TP/SERVER/SA/BV-11-C from SDP Specification.

        @return True if test passes, False if test fails

        """
        return self.test_attribute(self.GAP_CLASS_ID,
                                   self.ICON_URL_ATTR_ID,
                                   self.BLUEZ_URL)


    def test_documentation_url_attribute(self):
        """Implementation of test TP/SERVER/SA/BV-18-C from SDP Specification.

        @return True if test passes, False if test fails

        """
        return self.test_attribute(self.GAP_CLASS_ID,
                                   self.DOCUMENTATION_URL_ATTR_ID,
                                   self.BLUEZ_URL)


    def test_client_executable_url_attribute(self):
        """Implementation of test TP/SERVER/SA/BV-19-C from SDP Specification.

        @return True if test passes, False if test fails

        """
        return self.test_attribute(self.GAP_CLASS_ID,
                                   self.CLIENT_EXECUTABLE_URL_ATTR_ID,
                                   self.BLUEZ_URL)


    def test_protocol_descriptor_list_attribute(self):
        """Implementation of test TP/SERVER/SA/BV-05-C from SDP Specification.

        @return True if test passes, False if test fails

        """
        return self.test_attribute(self.GAP_CLASS_ID,
                                   self.PROTOCOL_DESCRIPTOR_LIST_ATTR_ID,
                                   [[self.L2CAP_UUID, 31],
                                    [self.ATT_UUID, 1, 8]])


    def test_continuation_state(self):
        """Implementation of test TP/SERVER/SA/BV-03-C from SDP Specification.

        @return True if test passes, False if test fails

        """
        record_handle = self.get_single_handle(self.PNP_INFORMATION_CLASS_ID)
        if record_handle == -1:
            return False

        res = self.tester.service_attribute_request(
                  record_handle, self.MIN_ATTR_BYTE_CNT, [[0, 0xFFFF]])

        return isinstance(res, list) and res != []


    def test_version_list_attribute(self):
        """Implementation of test TP/SERVER/SA/BV-15-C from SDP Specification.

        @return True if test passes, False if test fails

        """
        version_list = self.get_attribute(self.SDP_SERVER_CLASS_ID,
                                          self.VERSION_NUMBER_LIST_ATTR_ID)
        return isinstance(version_list, list) and version_list != []


    def test_service_database_state_attribute(self):
        """Implementation of test TP/SERVER/SA/BV-16-C from SDP Specification.

        @return True if test passes, False if test fails

        """
        state = self.get_attribute(self.SDP_SERVER_CLASS_ID,
                                   self.SERVICE_DATABASE_STATE_ATTR_ID)
        return isinstance(state, int)


    def test_profile_descriptor_list_attribute(self):
        """Implementation of test TP/SERVER/SA/BV-17-C from SDP Specification.

        @return True if test passes, False if test fails

        """
        profile_list = self.get_attribute(self.PNP_INFORMATION_CLASS_ID,
                                          self.PROFILE_DESCRIPTOR_LIST_ATTR_ID)
        return (isinstance(profile_list, list) and len(profile_list) == 1 and
                isinstance(profile_list[0], list) and
                len(profile_list[0]) == 2 and
                profile_list[0][0] == self.PNP_INFORMATION_CLASS_ID)


    def test_additional_protocol_descriptor_list_attribute(self):
        """Implementation of test TP/SERVER/SA/BV-21-C from SDP Specification.

        @return True if test passes, False if test fails

        """
        protocol_list = self.get_attribute(self.AVRCP_TG_CLASS_ID,
                                           self.ADDITIONAL_PROTOCOLLIST_ATTR_ID)
        return isinstance(protocol_list, list) and protocol_list != []


    def test_non_existing_attribute(self):
        """Implementation of test TP/SERVER/SA/BV-20-C from SDP Specification.

        @return True if test passes, False if test fails

        """
        record_handle = self.get_single_handle(self.FAKE_SERVICE_CLASS_ID)
        if record_handle == -1:
            return False

        res = self.tester.service_attribute_request(
                  record_handle, self.MAX_ATTR_BYTE_CNT,
                  [self.NON_EXISTING_ATTRIBUTE_ID])

        return res == []


    def test_fake_attributes(self):
        """Test values of attributes of the fake service record.

        @return True if all tests pass, False otherwise

        """
        for attr_id in self.FAKE_GENERAL_ATTRIBUTE_IDS:
            if not self.test_attribute(self.FAKE_SERVICE_CLASS_ID,
                                       attr_id, self.FAKE_ATTRIBUTE_VALUE):
                return False

        for offset in self.FAKE_LANGUAGE_ATTRIBUTE_OFFSETS:
            record_handle = self.get_single_handle(self.FAKE_SERVICE_CLASS_ID)
            if record_handle == -1:
                return False

            lang_base = self.tester.service_attribute_request(
                            record_handle, self.MAX_ATTR_BYTE_CNT,
                            [self.LANGUAGE_BASE_ATTRIBUTE_ID])
            attr_id = lang_base[1] + offset

            response = self.tester.service_attribute_request(
                           record_handle, self.MAX_ATTR_BYTE_CNT, [attr_id])

            if response != [attr_id, self.FAKE_ATTRIBUTE_VALUE]:
                return False

        return True


    def test_invalid_record_handle(self):
        """Implementation of test TP/SERVER/SA/BI-01-C from SDP Specification.

        @return True if test passes, False if test fails

        """
        res = self.tester.service_attribute_request(
                  self.INVALID_RECORD_HANDLE, self.MAX_ATTR_BYTE_CNT,
                  [self.NON_EXISTING_ATTRIBUTE_ID])

        return res == self.ERROR_CODE_INVALID_RECORD_HANDLE


    def test_invalid_request_syntax(self):
        """Implementation of test TP/SERVER/SA/BI-02-C from SDP Specification.

        @return True if test passes, False if test fails

        """
        record_handle = self.get_single_handle(self.SDP_SERVER_CLASS_ID)
        if record_handle == -1:
            return False

        res = self.tester.service_attribute_request(
                  record_handle,
                  self.MAX_ATTR_BYTE_CNT,
                  [self.SERVICE_RECORD_HANDLE_ATTR_ID],
                  invalid_request=self.INVALID_SYNTAX_REQUEST)

        return res == self.ERROR_CODE_INVALID_SYNTAX


    def test_invalid_pdu_size(self):
        """Implementation of test TP/SERVER/SA/BI-03-C from SDP Specification.

        @return True if test passes, False if test fails

        """
        record_handle = self.get_single_handle(self.SDP_SERVER_CLASS_ID)
        if record_handle == -1:
            return False

        res = self.tester.service_attribute_request(
                  record_handle,
                  self.MAX_ATTR_BYTE_CNT,
                  [self.SERVICE_RECORD_HANDLE_ATTR_ID],
                  forced_pdu_size=self.INVALID_PDU_SIZE)

        return res == self.ERROR_CODE_INVALID_PDU_SIZE


    def correct_request(self):
        """Run basic tests for Service Attribute Request.

        @return True if all tests finishes correctly, False otherwise

        """
        # Connect to the DUT via L2CAP using SDP socket.
        self.tester.connect(self.adapter['Address'])

        return (self.test_record_handle_attribute() and
                self.test_browse_group_attribute() and
                self.test_icon_url_attribute() and
                self.test_documentation_url_attribute() and
                self.test_client_executable_url_attribute() and
                self.test_protocol_descriptor_list_attribute() and
                self.test_continuation_state() and
                self.test_version_list_attribute() and
                self.test_service_database_state_attribute() and
                self.test_profile_descriptor_list_attribute() and
                self.test_additional_protocol_descriptor_list_attribute() and
                self.test_fake_attributes() and
                self.test_non_existing_attribute() and
                self.test_invalid_record_handle() and
                self.test_invalid_request_syntax() and
                self.test_invalid_pdu_size())


    def build_service_record(self):
        """Build SDP record manually for the fake service.

        @return resulting record as string

        """
        value = ET.Element('uint16', {'value': str(self.FAKE_ATTRIBUTE_VALUE)})

        sdp_record = ET.Element('record')

        service_id_attr = ET.Element(
            'attribute', {'id': str(self.SERVICE_CLASS_ID_ATTR_ID)})
        service_id_attr.append(
            ET.Element('uuid', {'value': '0x%X' % self.FAKE_SERVICE_CLASS_ID}))
        sdp_record.append(service_id_attr)

        for attr_id in self.FAKE_GENERAL_ATTRIBUTE_IDS:
            attr = ET.Element('attribute', {'id': str(attr_id)})
            attr.append(value)
            sdp_record.append(attr)

        for offset in self.FAKE_LANGUAGE_ATTRIBUTE_OFFSETS:
            attr_id = self.FAKE_ATTRIBUTE_VALUE + offset
            attr = ET.Element('attribute', {'id': str(attr_id)})
            attr.append(value)
            sdp_record.append(attr)

        sdp_record_str = ('<?xml version="1.0" encoding="UTF-8"?>' +
                          ET.tostring(sdp_record))
        return sdp_record_str


    def run_once(self):
        # Reset the adapter to the powered on, discoverable state.
        if not (self.device.reset_on() and
                self.device.set_discoverable(True)):
            raise error.TestFail('DUT could not be reset to initial state')

        self.adapter = self.device.get_adapter_properties()

        # Create a fake service record in order to test attributes,
        # that are not present in any of existing services.
        uuid128 = ((self.FAKE_SERVICE_CLASS_ID << 96) +
                   self.BLUETOOTH_BASE_UUID)
        uuid_str = str(uuid.UUID(int=uuid128))
        sdp_record = self.build_service_record()
        self.device.register_profile(self.FAKE_SERVICE_PATH,
                                     uuid_str,
                                     {"ServiceRecord": sdp_record})

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
