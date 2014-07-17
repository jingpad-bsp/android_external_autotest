# Copyright (c) 2014 The Chromium OS Authors. All rights reserved.
# Use of this source code is governed by a BSD-style license that can be
# found in the LICENSE file.

"""
This module implements the classes for control message headers, control
messages and bidirectional process to pack and unpack request/response message
packets.
This module contains the following classes: |MBIMData|, |MBIMHeader|,
|MBIMFragmentHeader|, |MBIMMessageBase|, |MBIMMessage|, |MBIMOpenMessage|,
|MBIMCloseMessage|, |MBIMCommandMessage|, |MBIMErrorMessage|, |MBIMOpenDone|,
|MBIMCloseDone|, |MBIMCommandDone|.

Reference:
    [1] Universal Serial Bus Communications Class Subclass Specification for
        Mobile Broadband Interface Model
        http://www.usb.org/developers/docs/devclass_docs/
        MBIM10Errata1_073013.zip
"""
import array
import struct
import sys

import common
from autotest_lib.client.cros.cellular.mbim_compliance import mbim_errors


# The following type values are defined for the MBIM control messages sent from
# the host to the device.
MBIM_OPEN_MSG = 0x00000001
MBIM_CLOSE_MSG = 0x00000002
MBIM_COMMAND_MSG = 0x00000003
MBIM_HOST_ERROR_MSG = 0x00000004

# The following type values are defined for the MBIM control messages sent from
# the device to the host.
MBIM_OPEN_DONE = 0x80000001
MBIM_CLOSE_DONE = 0x80000002
MBIM_COMMAND_DONE = 0x80000003
MBIM_FUNCTION_ERROR_MSG = 0x80000004
MBIM_INDICATE_STATUS_MSG = 0x80000005

# The following type values are defined for the MBIM status codes.
MBIM_STATUS_SUCCESS = 0x00000000


class MBIMData(object):
    """
    The base class for the data being used in control messages.

    Its derived classes should define |_FIELDS|, a set of tuples in
    (<field format>, <field name>) form, and |_DEFAULTS|, a dictionary to
    map field names to their default values. |_FIELDS| and |_DEFAULTS| are used
    to pack/unpack to/from packets which are sequences of bytes. Some derived
    class may define extra fields, such as |_COMMAND_INFORMATION| in
    |MBIMCommandMessage| and |MBIMCommandone|.
    There are three classes derived from |MBIMData|, |MBIMHeader|,
    |MBIMFragmentHeader| and |MBIMMessageBase|. Both |MBIMHeader| and
    |MBIMFragment| define fields which will be used in the headers for control
    messages. |MBIMMessageBase| is the base case for all control messages.
    """

    @classmethod
    def get_fields(cls, get_all=False):
        """
        @returns The set of the fields defined in |_FIELDS| of a derived class.
        """
        return cls._FIELDS


    @classmethod
    def unpack(cls, packet):
        """
        Unpack the packet into a map with the formats specified in |fields|. The
        map contains pairs <field_name>: <value>.

        @param packet: The byte array to be unpacked.
        @returns The contents for the packet in a dictionary, where the pairs
                are in <field_name>: <value> form.

        """
        field_formats, field_names = zip(*cls.get_fields(get_all=True))
        format_string = '<' + ''.join(field_formats)
        length_of_fields = struct.calcsize(format_string)

        if len(packet) < length_of_fields:
            mbim_errors.log_and_raise(
                    mbim_errors.MBIMComplianceControlMessageError,
                    'The length of the packet should be at least %d for %s, '
                    'got %d.' % (length_of_fields, cls.__name__, len(packet)))

        contents = {}
        for index, value in enumerate(struct.unpack(format_string,
                                                    packet[:length_of_fields])):
            contents[field_names[index]] = value
        return contents


class MBIMHeader(MBIMData):
    """ The header class for MBIM control messages."""

    _FIELDS = (('I', 'message_type'),
               ('I', 'message_length'),
               ('I', 'transaction_id'))


class MBIMFragmentHeader(MBIMData):
    """ The fragment header class for MBIM control messages."""

    _FIELDS = (('I', 'total_fragments'),
               ('I', 'current_fragment'))


class MBIMMessageBase(MBIMData):
    """
    This class is the base class for all MBIM control messages.

    This class provides functions including packet production and packets
    parsing. The instantiation of its derived classes depends on |_FIELDS| and
    |_DEFAULTS| defined in the derived classes, where the |MBIMCommandMessage|
    has extra fields defined as |_COMMAND_INFORMATION|.
    |_FIELDS| defines the essential fields including message type, message
    length, transaction ID, and some message-specific fields.
    |_COMMAND_INFORMATION| defines the information about device service ID, CID,
    command type and length of the information buffer.
    |_DEFAULTS| specifies the default values for some fields. Note that
    message type is required for every derived class of |MBIMMessageBase|, and
    for |MBIMCommandMessage|, total fragment, current fragment, and information
    buffer length are required.
    """
    _transaction_id = 0x00000000


    def __init__(self, **kwargs):
        """
        @param kwargs: The keyword arguments for all the fields to be set in the
        message body.
        """
        keys = kwargs.keys()
        defaults = self._DEFAULTS
        self.all_field_formats, self.all_field_names = (
                zip(*self.get_fields(get_all=True)))

        unknown_keys = set(keys) - set(self.all_field_names)
        if unknown_keys:
            mbim_errors.log_and_raise(
                    mbim_errors.MBIMComplianceControlMessageError,
                    'Unknown field(s) %s found in arguments for %s.' % (
                            unknown_keys, self.__class__.__name__))

        if self.__class__ in [MBIMOpenDone, MBIMCloseDone, MBIMCommandDone]:
            optional_fields = set()
        else:
            optional_fields = set(['transaction_id', 'message_length',
                                   'total_fragments', 'current_fragment'])
        required_fields = (set(self.all_field_names) - optional_fields)

        for name in required_fields:
            # Set the field value to the value given in |kwargs| if the value
            # is provided, default value otherwise. If default value is not
            # provided as well, an error will be raised.
            value = kwargs.get(name, defaults.get(name))
            if value is None:
                mbim_errors.log_and_raise(
                        mbim_errors.MBIMComplianceControlMessageError,
                        'Field %s is required to create a %s.' % (
                                name, self.__class__.__name__))
            setattr(self, name, value)


    def _get_transaction_id(self):
        """
        Returns incrementing transaction ids on successive calls.

        @returns The tracsaction id for control message delivery.

        """
        if MBIMMessageBase._transaction_id > (sys.maxint - 2):
            MBIMMessageBase._transaction_id = 0x00000000
        MBIMMessageBase._transaction_id += 1
        return MBIMMessageBase._transaction_id


    def generate_packets(self):
        """
        Generate a list of packets based on the given message type. Different
        types of messages require different fields. For example, a MBIM_OPEN_MSG
        will need message_type and max_control_transfer to contruct the message.

        @returns A list of packets to be sent, and each packet is in binary
                array form.
        """
        # TODO(mcchou): Handle the fragmentation for MBIM_COMMAND_MSG while
        #               information buffer is not NULL.
        cls = self.__class__
        packets = []
        self.transaction_id = self._get_transaction_id()
        if cls in [MBIMOpenMessage, MBIMCloseMessage, MBIMHostErrorMessage,
                   MBIMCommandMessage]:
            format_string = '<' + ''.join(self.all_field_formats)
            self.message_length = struct.calcsize(format_string)
            packets.append(self.pack(format_string, self.all_field_names))
        return packets


    def pack(self, format_string, field_names):
        """
        Pack a list of fields based on their formats.

        @param format_string: The concatenated formats for the fields given in
                |field_names|.
        @param field_names: The name of the fields to be packed.
        @returns The packet in binary array form.

        """
        field_values = [getattr(self, name) for name in field_names]
        return array.array('B', struct.pack(format_string, *field_values))


    @classmethod
    def get_fields(cls, get_all=False):
        """
        Retrieve the fields based on the type of the control message. For
        |MBIMOpenMessage|, |MBIMCloseMessage| and  |MBIMErrorMessage|, there is
        no |_COMMAND_INFORMATION|, so this method returns fields in |_FIELDS|
        even if |get_all|=True. As for |MBIMCommandMessage|, this method returns
        fields in both |_FIELDS| and |_COMMAND_INFORMATION| if |get_all|=True,
        |_FIELDS| otherwise.

        @param get_all: The flag to determine whether |_COMMAND_INTFORMATION|
                should be returned or not.
        @returns The set of the fields in tuple(field format, field name) form.

        """
        all_fields = cls._FIELDS
        if cls in [MBIMCommandMessage, MBIMCommandDone] and get_all:
            all_fields += cls._COMMAND_INFORMATION
        return all_fields


    @classmethod
    def parse_packets(cls, packets):
        """
        Parse a sequence of packets into the corresponding response message.

        Each packet is a byte array, and the response message can be one of
        the following type: |MBIMOpenDone|, |MBIMCloseDone| and
        |MBIMCommandDone|. For |MBIMOpenDone| and |MBIMCloseDone|, the expected
        number of packets is 1. As for |MBIMCommandDone|, the number of packets
        should be at least 1, since the response message from the device may be
        fragmented into several packetes.

        @param packets: The list of the response packets which are in byte
                array form.
        @returns The object of the response message. A response message can be
                one of the following type: |MBIMOpenDone|, |MBIMCloseDone| and
                |MBIMCommandDone|.

        """
        # Parse the first packet.
        response_contents = cls.unpack(packets[0])
        response_message = cls(**response_contents)
        field_formats, _ = zip(*cls.get_fields(get_all=True))
        length_of_all_fields = struct.calcsize('<' + ''.join(field_formats))

        if cls is MBIMCommandDone and len(packets) > 1:
            # Unpack the continuation packets of type |MBIM_COMMAND_DONE|.
            info_buffer = array.array('B')
            info_buffer.extend(packets[0][length_of_all_fields:])
            field_formats, field_names = zip(*cls.get_fields())
            format_string = '<' + ''.join(field_formats)
            length_of_headers = struct.calcsize(format_string)
            for packet in packets[1:]:
                if len(packet) < length_of_headers:
                    mbim_errors.log_and_raise(
                            mbim_errors.MBIMComplianceControlMessageError,
                            'The length of the continuation packet(s) for %s '
                            'should be at least %d.' % (
                                    cls.__name__, length_of_headers))

                info_buffer.extend(packet[length_of_headers:])
            setattr(response_message, 'information_buffer', info_buffer)

        elif cls not in [MBIMOpenDone, MBIMCloseDone]:
            mbim_errors.log_and_raise(NotImplementedError)

        return response_message


class MBIMOpenMessage(MBIMMessageBase):
    """ The class for MBIM_OPEN_MSG. """

    _FIELDS = MBIMHeader.get_fields() + (('I', 'max_control_transfer'),)
    _DEFAULTS = {'message_type': MBIM_OPEN_MSG}


class MBIMCloseMessage(MBIMMessageBase):
    """ The class for MBIM_CLOSE_MSG. """

    _FIELDS = MBIMHeader.get_fields()
    _DEFAULTS = {'message_type': MBIM_CLOSE_MSG}


class MBIMCommandMessage(MBIMMessageBase):
    """ The class for MBIM_COMMAND_MSG. """

    _FIELDS = MBIMHeader.get_fields() + MBIMFragmentHeader.get_fields()
    _COMMAND_INFORMATION = (('16s', 'device_service_id'),
                            ('I', 'cid'),
                            ('I', 'command_type'),
                            ('I', 'information_buffer_length'))
    _DEFAULTS = {'message_type': MBIM_COMMAND_MSG,
                 'total_fragment': 0x00000001,
                 'current_fragment': 0x00000000,
                 'information_buffer_length': 0}


class MBIMHostErrorMessage(MBIMMessageBase):
    """ The class for MBIM_ERROR_MSG. """

    _FIELDS = MBIMHeader.get_fields() + (('I', 'error_status_code'),)
    _DEFAULTS = {'message_type': MBIM_HOST_ERROR_MSG}


class MBIMOpenDone(MBIMMessageBase):
    """ The class for MBIM_OPEN_DONE. """

    _FIELDS = MBIMHeader.get_fields() + (('I', 'status_codes'),)
    _DEFAULTS = {'message_type': MBIM_OPEN_DONE}


class MBIMCloseDone(MBIMMessageBase):
    """ The class for MBIM_CLOSE_DONE. """

    _FIELDS = MBIMHeader.get_fields() + (('I', 'status_codes'),)
    _DEFAULTS = {'message_type': MBIM_CLOSE_DONE}


class MBIMCommandDone(MBIMMessageBase):
    """ The class for MBIM_COMMAND_DONE. """

    _FIELDS = MBIMHeader.get_fields() + MBIMFragmentHeader.get_fields()
    _COMMAND_INFORMATION = (('16s', 'device_service_id'),
                            ('I', 'cid'),
                            ('I', 'status'),
                            ('I', 'information_buffer_length'))
    _DEFAULTS = {'message_type': MBIM_COMMAND_DONE}



def parse_response_packets(packets):
    """
    Parse the response packets based on the response message type.

    @param packets: The list of packets to be parsed. Each packet is in byte
            array form.
    @returns The object of the response message. A response message can be
            one of the following type: |MBIMOpenDone|, |MBIMCloseDone| and
            |MBIMCommandDone|.

    """
    # TODO(mcchou): Handle the fragmented MBIM_COMMAND_DONE response and come up
    #               with a generic parser.
    if not packets:
        mbim_errors.log_and_raise(mbim_errors.MBIMComplianceControlMessageError,
                                  'Expected at least 1 packet to parse, got 0.')

    # Parse the packet header to get the response message type.
    header_contents = MBIMHeader.unpack(packets[0])

    # Parse |packets| based on the response message type.
    PARSER_MAP = {MBIM_OPEN_DONE: MBIMOpenDone.parse_packets,
                  MBIM_CLOSE_DONE: MBIMCloseDone.parse_packets,
                  MBIM_COMMAND_DONE: MBIMCommandDone.parse_packets}
    message_type = header_contents['message_type']
    parser = PARSER_MAP.get(message_type)

    if parser is None:
        mbim_errors.log_and_raise(NotImplementedError)

    response_message = parser(packets)
    return response_message
