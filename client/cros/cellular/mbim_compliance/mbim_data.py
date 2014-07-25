# Copyright (c) 2014 The Chromium OS Authors. All rights reserved.
# Use of this source code is governed by a BSD-style license that can be
# found in the LICENSE file.

"""
This module implements the classes for information structures encapsulated in
either |MBIMCommandMessage| or |MBIMCommandDone|.

Reference:
    [1] Universal Serial Bus Communications Class Subclass Specification for
        Mobile Broadband Interface Model
        http://www.usb.org/developers/docs/devclass_docs/
        MBIM10Errata1_073013.zip
"""
import array
import struct

import common
from autotest_lib.client.cros.cellular.mbim_compliance import mbim_control
from autotest_lib.client.cros.cellular.mbim_compliance import mbim_errors


class MBIMInformationBuffer(mbim_control.MBIMData):
    """
    The base class for structures in information buffers of control messages.
    """

    def __init__(self, data_buffer=None, **kwargs):
        """
        @param kwargs: The keyword arguments for all the fields to be set in the
                information structure body.
        """
        # TODO(mcchou): The creation of |MBIMDeviceServicesInfoStructure| should
        #         be handled separately, since field |device_services_ref_list|
        #         depends on the number of |device_services_count|.
        if self.__class__ is MBIMDeviceServicesInfoStructure:
            mbim_errors.log_and_raise(NotImplementedError)

        keys = kwargs.keys()
        self.all_field_formats, self.all_field_names = zip(*self._FIELDS)
        self.format_string = '<' + ''.join(self.all_field_formats)
        unknown_keys = set(keys) - set(self.all_field_names)
        if unknown_keys:
            mbim_errors.log_and_raise(
                    mbim_errors.MBIMComplianceControlMessageError,
                    'Unknown field(s) %s found in arguments for %s.' % (
                            list(unknown_keys), self.__class__.__name__))

        for name in self.all_field_names:
            # Set the field value to the value given in |kwargs| if the value is
            # provided, otherwise an error will be raised.
            value = kwargs.get(name)
            if value is None:
                mbim_errors.log_and_raise(
                        mbim_errors.MBIMComplianceControlMessageError,
                        'Field %s is required to create a %s.' % (
                                name, self.__class__.__name__))

            setattr(self, name, value)
        setattr(self, 'data_buffer', data_buffer)


    def pack(self):
        """
        Pack a list of fields based on their formats.

        @returns The information structure in binary array form.
        """
        field_values = [getattr(self, name) for name in self.all_field_names]
        byte_array = array.array('B', struct.pack(
                self.format_string, *field_values))
        if self.data_buffer:
            byte_array.extend(self.data_buffer)
        return byte_array


class MBIMSetConnectStructure(MBIMInformationBuffer):
    """ The class for MBIM_SET_CONNECT structure. """

    _FIELDS = (('I', 'session_id'),
               ('I', 'activation_command'),
               ('I', 'access_string_offset'),
               ('I', 'access_string_size'),
               ('I', 'user_name_offset'),
               ('I', 'user_name_size'),
               ('I', 'password_offset'),
               ('I', 'password_size'),
               ('I', 'compression'),
               ('I', 'auth_protocol'),
               ('I', 'ip_type'),
               ('16s', 'context_type'))


class MBIMConnectInfoStructure(MBIMInformationBuffer):
    """ The class for MBIM_CONNECT_INFO structure. """

    _FIELDS = (('I', 'session_id'),
               ('I', 'activation_state'),
               ('I', 'voice_call_state'),
               ('I', 'ip_type'),
               ('16s', 'context_type'),
               ('I', 'nw_error'))


class MBIMDeviceCapsInfoStructure(MBIMInformationBuffer):
    """ The class for MBIM_DEVICE_CAPS_INFO structure. """

    _FIELDS = (('I', 'device_type'),
               ('I', 'cellular_class'),
               ('I', 'voice_class'),
               ('I', 'sim_class'),
               ('I', 'data_class'),
               ('I', 'sms_caps'),
               ('I', 'control_caps'),
               ('I', 'max_sessions'),
               ('I', 'custom_data_class_offset'),
               ('I', 'custom_data_class_size'),
               ('I', 'device_id_offset'),
               ('I', 'device_id_size'),
               ('I', 'firmware_info_offset'),
               ('I', 'firmware_info_size'),
               ('I', 'hardware_info_offset'),
               ('I', 'hardware_info_size'))


class MBIMDeviceServicesInfoStructure(MBIMInformationBuffer):
    """ The class for MBIM_DEVICE_SERVICES_INFO structure. """

    # The length of |device_services_ref_list| depends on the value of
    # |device_services_count|.
    _FIELDS = (('I', 'device_services_count'),
               ('I', 'max_dss_sessions'),
               ('Q', 'device_services_ref_list'))


class MBIMRadioStateInfoStructure(MBIMInformationBuffer):
    """ The class for MBIM_RADIO_STATE_INFO structure. """

    _FIELDS = (('I', 'hw_radio_state'),
               ('I', 'sw_radio_state'))


class MBIMIPConfigurationInfoStructure(MBIMInformationBuffer):
    """ The class for MBIM_IP_CONFIGURATION_INFO structure. """

    _FIELDS = (('I', 'session_id'),
               ('I', 'ipv4_configuration_available'),
               ('I', 'ipv6_configuration_available'),
               ('I', 'ipv4_address_count'),
               ('I', 'ipv4_address_offset'),
               ('I', 'ipv6_address_count'),
               ('I', 'ipv6_address_offset'),
               ('I', 'ipv4_gateway_offset'),
               ('I', 'ipv6_gateway_offset'),
               ('I', 'ipv4_dns_server_count'),
               ('I', 'ipv4_dns_server_offset'),
               ('I', 'ipv6_dns_server_count'),
               ('I', 'ipv6_dns_server_offset'),
               ('I', 'ipv4_mtu'),
               ('I', 'ipv6_mtu'))
