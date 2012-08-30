# Copyright (c) 2012 The Chromium OS Authors. All rights reserved.
# Use of this source code is governed by a BSD-style license that can be
# found in the LICENSE file.

"""
Tools for serializing and deserializing DHCP packets.

DhcpPacket is a class that represents a single DHCP packet and contains some
logic to create and parse binary strings containing on the wire DHCP packets.

While you could call the constructor explicitly, most users should use the
static factories to construct packets with reasonable default values in most of
the fields, even if those values are zeros.

For example:

packet = dhcp_packet.create_offer_packet(transaction_id,
                                         hwmac_addr,
                                         offer_ip,
                                         offer_mask,
                                         server_ip,
                                         lease_time_seconds)
socket = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
# I believe that sending to the broadcast address needs special permissions.
socket.sendto(response_packet.to_binary_string(),
              ("255.255.255.255", 68))

Note that if you make changes, make sure that the tests in the bottom of this
file still pass.
"""

import logging
import random
import socket
import struct

class Option(object):
    """
    Represents an option in a DHCP packet.  Options may or may not be present
    and are not parsed into any particular format.  This means that the value of
    options is always in the form of a byte string.
    """
    def __init__(self, name, number, size):
        super(Option, self).__init__()
        self._name = name
        self._number = number
        self._size = size

    @property
    def name(self):
        return self._name

    @property
    def number(self):
        """
        Every DHCP option has a number that goes into the packet to indicate
        which particular option is being encoded in the next few bytes.  This
        property returns that number for each option.
        """
        return self._number

    @property
    def size(self):
        """
        The size property is a hint for what kind of size we might expect the
        option to be.  For instance, options with a size of 1 are expected to
        always be 1 byte long.  Negative sizes are variable length fields that
        are expected to be at least abs(size) bytes long.

        However, the size property is just a hint, and is not enforced or
        checked in any way.
        """
        return self._size


class Field(object):
    """
    Represents a required field in a DHCP packet.  Unlike options, we sometimes
    parse fields into more meaningful data types.  For instance, the hardware
    type field in an IPv4 packet is parsed into an int rather than being left as
    a raw byte string of length 1.
    """
    def __init__(self, name, wire_format, offset, size):
        super(Field, self).__init__()
        self._name = name
        self._wire_format = wire_format
        self._offset = offset
        self._size = size

    @property
    def name(self):
        return self._name

    @property
    def wire_format(self):
        """
        The wire format for a field defines how it will be parsed out of a DHCP
        packet.
        """
        return self._wire_format

    @property
    def offset(self):
        """
        The |offset| for a field defines the starting byte of the field in the
        binary packet string.  |offset| is using during parsing, along with
        |size| to extract the byte string of a field.
        """
        return self._offset

    @property
    def size(self):
        """
        Fields in DHCP packets have a fixed size that must be respected.  This
        size property is used in parsing to indicate that |self._size| number of
        bytes make up this field.
        """
        return self._size


# This is per RFC 2131.  The wording doesn't seem to say that the packets must
# be this big, but that has been the historic assumption in implementations.
DHCP_MIN_PACKET_SIZE = 300

IPV4_NULL_ADDRESS = "\x00\x00\x00\x00"

# These are required in every DHCP packet.  Without these fields, the
# packet will not even pass DhcpPacket.is_valid
FIELD_OP = Field("op", "!B", 0, 1)
FIELD_HWTYPE = Field("htype", "!B", 1, 1)
FIELD_HWADDR_LEN = Field("hlen", "!B", 2, 1)
FIELD_RELAY_HOPS = Field("hops", "!B", 3, 1)
FIELD_TRANSACTION_ID = Field("xid", "!I", 4, 4)
FIELD_TIME_SINCE_START = Field("secs", "!H", 8, 2)
FIELD_FLAGS = Field("flags", "!H", 10, 2)
FIELD_CLIENT_IP = Field("ciaddr", "!4s", 12, 4)
FIELD_YOUR_IP = Field("yiaddr", "!4s", 16, 4)
FIELD_SERVER_IP = Field("siaddr", "!4s", 20, 4)
FIELD_GATEWAY_IP = Field("giaddr", "!4s", 24, 4)
FIELD_CLIENT_HWADDR = Field("chaddr", "!16s", 28, 16)
# For legacy BOOTP reasons, there are 192 octets of 0's that
# come after the chaddr.
FIELD_MAGIC_COOKIE = Field("magic_cookie", "!I", 236, 4)

OPTION_TIME_OFFSET = Option("time_offset", 2, 4)
OPTION_ROUTERS = Option("routers", 3, -4)
OPTION_SUBNET_MASK = Option("subnet_mask", 1, 4)
# These *_servers (and router) options are actually lists of IPv4
# addressesexpected to be multiples of 4 octets.
OPTION_TIME_SERVERS = Option("time_servers", 4, -4)
OPTION_NAME_SERVERS = Option("name_servers", 5, -4)
OPTION_DNS_SERVERS = Option("dns_servers", 6, -4)
OPTION_LOG_SERVERS = Option("log_servers", 7, -4)
OPTION_COOKIE_SERVERS = Option("cookie_servers", 8, -4)
OPTION_LPR_SERVERS = Option("lpr_servers", 9, -4)
OPTION_IMPRESS_SERVERS = Option("impress_servers", 10, -4)
OPTION_RESOURCE_LOC_SERVERS = Option("resource_loc_servers", 11, -4)
OPTION_HOST_NAME = Option("host_name", 12, -1)
OPTION_BOOT_FILE_SIZE = Option("boot_file_size", 13, 2)
OPTION_MERIT_DUMP_FILE = Option("merit_dump_file", 14, -1)
OPTION_SWAP_SERVER = Option("domain_name", 15, -1)
OPTION_DOMAIN_NAME = Option("swap_server", 16, 4)
OPTION_ROOT_PATH = Option("root_path", 17, -1)
OPTION_EXTENSIONS = Option("extensions", 18, -1)
# DHCP options.
OPTION_REQUESTED_IP = Option("requested_ip", 50, 4)
OPTION_IP_LEASE_TIME = Option("ip_lease_time", 51, 4)
OPTION_OPTION_OVERLOAD = Option("option_overload", 52, 1)
OPTION_DHCP_MESSAGE_TYPE = Option("dhcp_message_type", 53, 1)
OPTION_SERVER_ID = Option("server_id", 54, 4)
OPTION_PARAMETER_REQUEST_LIST = Option("parameter_request_list", 55, -1)
OPTION_MESSAGE = Option("message", 56, -1)
OPTION_MAX_DHCP_MESSAGE_SIZE = Option("max_dhcp_message_size", 57, 2)
OPTION_RENEWAL_T1_TIME_VALUE = Option("renewal_t1_time_value", 58, 4)
OPTION_REBINDING_T2_TIME_VALUE = Option("rebinding_t2_time_value", 59, 4)
OPTION_VENDOR_ID = Option("vendor_id", 60, -1)
OPTION_CLIENT_ID = Option("client_id", 61, -2)
OPTION_TFTP_SERVER_NAME = Option("tftp_server_name", 66, -1)
OPTION_BOOTFILE_NAME = Option("bootfile_name", 67, -1)
# Unlike every other option, which are tuples like:
# <number, length in bytes, data>, the pad and end options are just
# single bytes "\x00" and "\xff" (without length or data fields).
OPTION_PAD = 0
OPTION_END = 255

# All fields are required.
DHCP_PACKET_FIELDS = [
        FIELD_OP,
        FIELD_HWTYPE,
        FIELD_HWADDR_LEN,
        FIELD_RELAY_HOPS,
        FIELD_TRANSACTION_ID,
        FIELD_TIME_SINCE_START,
        FIELD_FLAGS,
        FIELD_CLIENT_IP,
        FIELD_YOUR_IP,
        FIELD_SERVER_IP,
        FIELD_GATEWAY_IP,
        FIELD_CLIENT_HWADDR,
        FIELD_MAGIC_COOKIE,
        ]
# The op field in an ipv4 packet is either 1 or 2 depending on
# whether the packet is from a server or from a client.
FIELD_VALUE_OP_CLIENT_REQUEST = 1
FIELD_VALUE_OP_SERVER_RESPONSE = 2
# 1 == 10mb ethernet hardware address type (aka MAC).
FIELD_VALUE_HWTYPE_10MB_ETH = 1
# MAC addresses are still 6 bytes long.
FIELD_VALUE_HWADDR_LEN_10MB_ETH = 6
FIELD_VALUE_MAGIC_COOKIE = 0x63825363

OPTIONS_START_OFFSET = 240
# From RFC2132, the valid DHCP message types are:
OPTION_VALUE_DHCP_MESSAGE_TYPE_DISCOVERY = "\x01"
OPTION_VALUE_DHCP_MESSAGE_TYPE_OFFER     = "\x02"
OPTION_VALUE_DHCP_MESSAGE_TYPE_REQUEST   = "\x03"
OPTION_VALUE_DHCP_MESSAGE_TYPE_DECLINE   = "\x04"
OPTION_VALUE_DHCP_MESSAGE_TYPE_ACK       = "\x05"
OPTION_VALUE_DHCP_MESSAGE_TYPE_NAK       = "\x06"
OPTION_VALUE_DHCP_MESSAGE_TYPE_RELEASE   = "\x07"
OPTION_VALUE_DHCP_MESSAGE_TYPE_INFORM    = "\x08"

OPTION_VALUE_PARAMETER_REQUEST_LIST_DEFAULT = \
        chr(OPTION_SUBNET_MASK.number) + \
        chr(OPTION_ROUTERS.number) + \
        chr(OPTION_DNS_SERVERS.number) + \
        chr(OPTION_HOST_NAME.number)

# These are possible options that may not be in every packet.
# Frequently, the client can include a bunch of options that indicate
# that it would like to receive information about time servers, routers,
# lpr servers, and much more, but the DHCP server can usually ignore
# those requests.
#
# Eventually, each option is encoded as:
#     <option.number, option.size, [array of option.size bytes]>
# Unlike fields, which make up a fixed packet format, options can be in
# any order, except where they cannot.  For instance, option 1 must
# follow option 3 if both are supplied.  For this reason, potential
# options are in this list, and added to the packet in this order every
# time.
#
# size < 0 indicates that this is variable length field of at least
# abs(length) bytes in size.
DHCP_PACKET_OPTIONS = [
        OPTION_TIME_OFFSET,
        OPTION_ROUTERS,
        OPTION_SUBNET_MASK,
        # These *_servers (and router) options are actually lists of
        # IPv4 addresses expected to be multiples of 4 octets.
        OPTION_TIME_SERVERS,
        OPTION_NAME_SERVERS,
        OPTION_DNS_SERVERS,
        OPTION_LOG_SERVERS,
        OPTION_COOKIE_SERVERS,
        OPTION_LPR_SERVERS,
        OPTION_IMPRESS_SERVERS,
        OPTION_RESOURCE_LOC_SERVERS,
        OPTION_HOST_NAME,
        OPTION_BOOT_FILE_SIZE,
        OPTION_MERIT_DUMP_FILE,
        OPTION_SWAP_SERVER,
        OPTION_DOMAIN_NAME,
        OPTION_ROOT_PATH,
        OPTION_EXTENSIONS,
        # DHCP options.
        OPTION_REQUESTED_IP,
        OPTION_IP_LEASE_TIME,
        OPTION_OPTION_OVERLOAD,
        OPTION_DHCP_MESSAGE_TYPE,
        OPTION_SERVER_ID,
        OPTION_PARAMETER_REQUEST_LIST,
        OPTION_MESSAGE,
        OPTION_MAX_DHCP_MESSAGE_SIZE,
        OPTION_RENEWAL_T1_TIME_VALUE,
        OPTION_REBINDING_T2_TIME_VALUE,
        OPTION_VENDOR_ID,
        OPTION_CLIENT_ID,
        OPTION_TFTP_SERVER_NAME,
        OPTION_BOOTFILE_NAME,
        ]

def get_dhcp_option_by_number(number):
    for option in DHCP_PACKET_OPTIONS:
        if option.number == number:
            return option
    return None

class DhcpPacket(object):
    @staticmethod
    def create_discovery_packet(hwmac_addr):
        """
        Create a discovery packet.

        Fill in fields of a DHCP packet as if it were being sent from
        |hwmac_addr|.  Requests subnet masks, broadcast addresses, router
        addresses, dns addresses, domain search lists, client host name, and NTP
        server addresses.  Note that the offer packet received in response to
        this packet will probably not contain all of that information.
        """
        # MAC addresses are actually only 6 bytes long, however, for whatever
        # reason, DHCP allocated 12 bytes to this field.  Ease the burden on
        # developers and hide this detail.
        while len(hwmac_addr) < 12:
            hwmac_addr += chr(OPTION_PAD)

        packet = DhcpPacket()
        packet.set_field(FIELD_OP.name, FIELD_VALUE_OP_CLIENT_REQUEST)
        packet.set_field(FIELD_HWTYPE.name, FIELD_VALUE_HWTYPE_10MB_ETH)
        packet.set_field(FIELD_HWADDR_LEN.name, FIELD_VALUE_HWADDR_LEN_10MB_ETH)
        packet.set_field(FIELD_RELAY_HOPS.name, 0)
        packet.set_field(FIELD_TRANSACTION_ID.name, random.getrandbits(32))
        packet.set_field(FIELD_TIME_SINCE_START.name, 0)
        packet.set_field(FIELD_FLAGS.name, 0)
        packet.set_field(FIELD_CLIENT_IP.name, IPV4_NULL_ADDRESS)
        packet.set_field(FIELD_YOUR_IP.name, IPV4_NULL_ADDRESS)
        packet.set_field(FIELD_SERVER_IP.name, IPV4_NULL_ADDRESS)
        packet.set_field(FIELD_GATEWAY_IP.name, IPV4_NULL_ADDRESS)
        packet.set_field(FIELD_CLIENT_HWADDR.name, hwmac_addr)
        packet.set_field(FIELD_MAGIC_COOKIE.name, FIELD_VALUE_MAGIC_COOKIE)
        packet.set_option(OPTION_DHCP_MESSAGE_TYPE.name,
                          OPTION_VALUE_DHCP_MESSAGE_TYPE_DISCOVERY)
        packet.set_option(OPTION_PARAMETER_REQUEST_LIST.name,
                          OPTION_VALUE_PARAMETER_REQUEST_LIST_DEFAULT)

        return packet

    @staticmethod
    def create_offer_packet(transaction_id,
                            hwmac_addr,
                            offer_ip,
                            offer_subnet_mask,
                            server_ip,
                            lease_time_seconds):
        """
        Create an offer packet, given some fields that tie the packet to a
        particular offer.
        """
        packet = DhcpPacket()
        packet.set_field(FIELD_OP.name, FIELD_VALUE_OP_SERVER_RESPONSE)
        packet.set_field(FIELD_HWTYPE.name, FIELD_VALUE_HWTYPE_10MB_ETH)
        packet.set_field(FIELD_HWADDR_LEN.name, FIELD_VALUE_HWADDR_LEN_10MB_ETH)
        # This has something to do with relay agents
        packet.set_field(FIELD_RELAY_HOPS.name, 0)
        packet.set_field(FIELD_TRANSACTION_ID.name, transaction_id)
        packet.set_field(FIELD_TIME_SINCE_START.name, 0)
        packet.set_field(FIELD_FLAGS.name, 0)
        packet.set_field(FIELD_CLIENT_IP.name, IPV4_NULL_ADDRESS)
        packet.set_field(FIELD_YOUR_IP.name, socket.inet_aton(offer_ip))
        packet.set_field(FIELD_SERVER_IP.name, socket.inet_aton(server_ip))
        packet.set_field(FIELD_GATEWAY_IP.name, IPV4_NULL_ADDRESS)
        packet.set_field(FIELD_CLIENT_HWADDR.name, hwmac_addr)
        packet.set_field(FIELD_MAGIC_COOKIE.name, FIELD_VALUE_MAGIC_COOKIE)
        packet.set_option(OPTION_DHCP_MESSAGE_TYPE.name,
                          OPTION_VALUE_DHCP_MESSAGE_TYPE_OFFER)
        packet.set_option(OPTION_SUBNET_MASK.name,
                          socket.inet_aton(offer_subnet_mask))
        packet.set_option(OPTION_SERVER_ID.name, socket.inet_aton(server_ip))
        packet.set_option(OPTION_IP_LEASE_TIME.name,
                          struct.pack("!I", int(lease_time_seconds)))
        return packet

    @staticmethod
    def create_request_packet(transaction_id,
                              hwmac_addr,
                              requested_ip,
                              server_ip):
        packet = DhcpPacket()
        packet.set_field(FIELD_OP.name, FIELD_VALUE_OP_CLIENT_REQUEST)
        packet.set_field(FIELD_HWTYPE.name, FIELD_VALUE_HWTYPE_10MB_ETH)
        packet.set_field(FIELD_HWADDR_LEN.name, FIELD_VALUE_HWADDR_LEN_10MB_ETH)
        # This has something to do with relay agents
        packet.set_field(FIELD_RELAY_HOPS.name, 0)
        packet.set_field(FIELD_TRANSACTION_ID.name, transaction_id)
        packet.set_field(FIELD_TIME_SINCE_START.name, 0)
        packet.set_field(FIELD_FLAGS.name, 0)
        packet.set_field(FIELD_CLIENT_IP.name, IPV4_NULL_ADDRESS)
        packet.set_field(FIELD_YOUR_IP.name, IPV4_NULL_ADDRESS)
        packet.set_field(FIELD_SERVER_IP.name, IPV4_NULL_ADDRESS)
        packet.set_field(FIELD_GATEWAY_IP.name, IPV4_NULL_ADDRESS)
        packet.set_field(FIELD_CLIENT_HWADDR.name, hwmac_addr)
        packet.set_field(FIELD_MAGIC_COOKIE.name, FIELD_VALUE_MAGIC_COOKIE)
        packet.set_option(OPTION_REQUESTED_IP.name,
                          socket.inet_aton(requested_ip))
        packet.set_option(OPTION_DHCP_MESSAGE_TYPE.name,
                          OPTION_VALUE_DHCP_MESSAGE_TYPE_REQUEST)
        packet.set_option(OPTION_SERVER_ID.name, socket.inet_aton(server_ip))
        packet.set_option(OPTION_PARAMETER_REQUEST_LIST.name,
                          OPTION_VALUE_PARAMETER_REQUEST_LIST_DEFAULT)
        return packet

    @staticmethod
    def create_acknowledgement_packet(transaction_id,
                                      hwmac_addr,
                                      granted_ip,
                                      granted_ip_subnet_mask,
                                      server_ip,
                                      lease_time_seconds):
        packet = DhcpPacket()
        packet.set_field(FIELD_OP.name, FIELD_VALUE_OP_SERVER_RESPONSE)
        packet.set_field(FIELD_HWTYPE.name, FIELD_VALUE_HWTYPE_10MB_ETH)
        packet.set_field(FIELD_HWADDR_LEN.name, FIELD_VALUE_HWADDR_LEN_10MB_ETH)
        # This has something to do with relay agents
        packet.set_field(FIELD_RELAY_HOPS.name, 0)
        packet.set_field(FIELD_TRANSACTION_ID.name, transaction_id)
        packet.set_field(FIELD_TIME_SINCE_START.name, 0)
        packet.set_field(FIELD_FLAGS.name, 0)
        packet.set_field(FIELD_CLIENT_IP.name, IPV4_NULL_ADDRESS)
        packet.set_field(FIELD_YOUR_IP.name, socket.inet_aton(granted_ip))
        packet.set_field(FIELD_SERVER_IP.name, socket.inet_aton(server_ip))
        packet.set_field(FIELD_GATEWAY_IP.name, IPV4_NULL_ADDRESS)
        packet.set_field(FIELD_CLIENT_HWADDR.name, hwmac_addr)
        packet.set_field(FIELD_MAGIC_COOKIE.name, FIELD_VALUE_MAGIC_COOKIE)
        packet.set_option(OPTION_DHCP_MESSAGE_TYPE.name,
                          OPTION_VALUE_DHCP_MESSAGE_TYPE_ACK)
        packet.set_option(OPTION_SUBNET_MASK.name,
                          socket.inet_aton(granted_ip_subnet_mask))
        packet.set_option(OPTION_SERVER_ID.name, socket.inet_aton(server_ip))
        packet.set_option(OPTION_IP_LEASE_TIME.name,
                          struct.pack("!I", int(lease_time_seconds)))
        return packet

    def __init__(self, byte_str=None):
        """
        Create a DhcpPacket, filling in fields from a byte string if given.

        Assumes that the packet starts at offset 0 in the binary string.  This
        includes the fields and options.  Fields are different from options in
        that we bother to decode these into more usable data types like
        integers rather than keeping them as raw byte strings.  Fields are also
        required to exist, unlike options which may not.

        Each option is encoded as a tuple <option number, length, data> where
        option number is a byte indicating the type of option, length indicates
        the number of bytes in the data for option, and data is a length array
        of bytes.  The only exceptions to this rule are the 0 and 255 options,
        which have 0 data length, and no length byte.  These tuples are then
        simply appended to each other.  This encoding is the same as the BOOTP
        vendor extention field encoding.
        """
        super(DhcpPacket, self).__init__()
        self._options = {}
        self._fields = {}
        self._logger = logging.getLogger("dhcp.packet")
        if byte_str is None:
            return
        if len(byte_str) < OPTIONS_START_OFFSET + 1:
            self._logger.error("Invalid byte string for packet.")
            return
        for field in DHCP_PACKET_FIELDS:
            self._fields[field.name] = struct.unpack(field.wire_format,
                                                     byte_str[field.offset :
                                                              field.offset +
                                                              field.size])[0]
        offset = OPTIONS_START_OFFSET
        while offset < len(byte_str) and ord(byte_str[offset]) != OPTION_END:
            data_type = ord(byte_str[offset])
            offset += 1
            if data_type == OPTION_PAD:
                continue
            data_length = ord(byte_str[offset])
            offset += 1
            data = byte_str[offset: offset + data_length]
            offset += data_length
            option_bunch = get_dhcp_option_by_number(data_type)
            if option_bunch is None:
                # Unsupported data type, of which we have many.
                continue
            self._options[option_bunch.name] = data

    @property
    def client_hw_address(self):
        return self._fields["chaddr"]

    @property
    def is_valid(self):
        for field in DHCP_PACKET_FIELDS:
            if (not field.name in self._fields or
                self._fields[field.name] is None):
                self._logger.info("Missing field %s in packet." % field.name)
                return False
        if (self._fields[FIELD_MAGIC_COOKIE.name] !=
            FIELD_VALUE_MAGIC_COOKIE):
            return False
        return True

    @property
    def message_type(self):
        if not "dhcp_message_type" in self._options:
            return -1
        return self._options["dhcp_message_type"]

    @property
    def transaction_id(self):
        return self._fields["xid"]

    def get_field(self, field_name):
        if field_name in self._fields:
            return self._fields[field_name]
        return None

    def get_option(self, option_name):
        if option_name in self._options:
            return self._options[option_name]
        return None

    def set_field(self, field_name, field_value):
        self._fields[field_name] = field_value

    def set_option(self, option_name, option_value):
        self._options[option_name] = option_value

    def to_binary_string(self):
        if not self.is_valid:
            return None
        # A list of byte strings to be joined into a single string at the end.
        data = []
        offset = 0
        for field in DHCP_PACKET_FIELDS:
            field_data = struct.pack(field.wire_format,
                                     self._fields[field.name])
            while offset < field.offset:
                # This should only happen when we're padding the fields because
                # we're not filling in legacy BOOTP stuff.
                data.append("\x00")
                offset += 1
            data.append(field_data)
            offset += field.size
        # Last field processed is the magic cookie, so we're ready for options.
        # Have to process options
        for option in DHCP_PACKET_OPTIONS:
            if not option.name in self._options:
                continue
            data.append(struct.pack("BB",
                                    option.number,
                                    len(self._options[option.name])))
            offset += 2
            data.append(self._options[option.name])
            offset += len(self._options[option.name])
        data.append(chr(OPTION_END))
        offset += 1
        while offset < DHCP_MIN_PACKET_SIZE:
            data.append(chr(OPTION_PAD))
            offset += 1
        return "".join(data)
