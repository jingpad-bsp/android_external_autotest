# Copyright (c) 2013 The Chromium OS Authors. All rights reserved.
# Use of this source code is governed by a BSD-style license that can be
# found in the LICENSE file.

import btsocket
import logging
import socket
import struct


# Constants from lib/mgmt.h in BlueZ source
MGMT_INDEX_NONE = 0xFFFF

MGMT_HDR_SIZE = 6

MGMT_STATUS_SUCCESS            = 0x00
MGMT_STATUS_UNKNOWN_COMMAND    = 0x01
MGMT_STATUS_NOT_CONNECTED      = 0x02
MGMT_STATUS_FAILED             = 0x03
MGMT_STATUS_CONNECT_FAILED     = 0x04
MGMT_STATUS_AUTH_FAILED        = 0x05
MGMT_STATUS_NOT_PAIRED         = 0x06
MGMT_STATUS_NO_RESOURCES       = 0x07
MGMT_STATUS_TIMEOUT            = 0x08
MGMT_STATUS_ALREADY_CONNECTED  = 0x09
MGMT_STATUS_BUSY               = 0x0a
MGMT_STATUS_REJECTED           = 0x0b
MGMT_STATUS_NOT_SUPPORTED      = 0x0c
MGMT_STATUS_INVALID_PARAMS     = 0x0d
MGMT_STATUS_DISCONNECTED       = 0x0e
MGMT_STATUS_NOT_POWERED        = 0x0f
MGMT_STATUS_CANCELLED          = 0x10
MGMT_STATUS_INVALID_INDEX      = 0x11

MGMT_OP_READ_VERSION           = 0x0001
MGMT_OP_READ_COMMANDS          = 0x0002
MGMT_OP_READ_INDEX_LIST        = 0x0003
MGMT_OP_READ_INFO              = 0x0004
MGMT_OP_SET_POWERED            = 0x0005
MGMT_OP_SET_DISCOVERABLE       = 0x0006
MGMT_OP_SET_CONNECTABLE        = 0x0007
MGMT_OP_SET_FAST_CONNECTABLE   = 0x0008
MGMT_OP_SET_PAIRABLE           = 0x0009
MGMT_OP_SET_LINK_SECURITY      = 0x000A
MGMT_OP_SET_SSP                = 0x000B
MGMT_OP_SET_HS                 = 0x000C
MGMT_OP_SET_LE                 = 0x000D
MGMT_OP_SET_DEV_CLASS          = 0x000E
MGMT_OP_SET_LOCAL_NAME         = 0x000F
MGMT_OP_ADD_UUID               = 0x0010
MGMT_OP_REMOVE_UUID            = 0x0011
MGMT_OP_LOAD_LINK_KEYS         = 0x0012
MGMT_OP_LOAD_LONG_TERM_KEYS    = 0x0013
MGMT_OP_DISCONNECT             = 0x0014
MGMT_OP_GET_CONNECTIONS        = 0x0015
MGMT_OP_PIN_CODE_REPLY         = 0x0016
MGMT_OP_PIN_CODE_NEG_REPLY     = 0x0017
MGMT_OP_SET_IO_CAPABILITY      = 0x0018
MGMT_OP_PAIR_DEVICE            = 0x0019
MGMT_OP_CANCEL_PAIR_DEVICE     = 0x001A
MGMT_OP_UNPAIR_DEVICE          = 0x001B
MGMT_OP_USER_CONFIRM_REPLY     = 0x001C
MGMT_OP_USER_CONFIRM_NEG_REPLY = 0x001D
MGMT_OP_USER_PASSKEY_REPLY     = 0x001E
MGMT_OP_USER_PASSKEY_NEG_REPLY = 0x001F
MGMT_OP_READ_LOCAL_OOB_DATA    = 0x0020
MGMT_OP_ADD_REMOTE_OOB_DATA    = 0x0021
MGMT_OP_REMOVE_REMOTE_OOB_DATA = 0x0022
MGMT_OP_START_DISCOVERY        = 0x0023
MGMT_OP_STOP_DISCOVERY         = 0x0024
MGMT_OP_CONFIRM_NAME           = 0x0025
MGMT_OP_BLOCK_DEVICE           = 0x0026
MGMT_OP_UNBLOCK_DEVICE         = 0x0027
MGMT_OP_SET_DEVICE_ID          = 0x0028

MGMT_EV_CMD_COMPLETE           = 0x0001
MGMT_EV_CMD_STATUS             = 0x0002
MGMT_EV_CONTROLLER_ERROR       = 0x0003
MGMT_EV_INDEX_ADDED            = 0x0004
MGMT_EV_INDEX_REMOVED          = 0x0005
MGMT_EV_NEW_SETTINGS           = 0x0006
MGMT_EV_CLASS_OF_DEV_CHANGED   = 0x0007
MGMT_EV_LOCAL_NAME_CHANGED     = 0x0008
MGMT_EV_NEW_LINK_KEY           = 0x0009
MGMT_EV_NEW_LONG_TERM_KEY      = 0x000A
MGMT_EV_DEVICE_CONNECTED       = 0x000B
MGMT_EV_DEVICE_DISCONNECTED    = 0x000C
MGMT_EV_CONNECT_FAILED         = 0x000D
MGMT_EV_PIN_CODE_REQUEST       = 0x000E
MGMT_EV_USER_CONFIRM_REQUEST   = 0x000F
MGMT_EV_USER_PASSKEY_REQUEST   = 0x0010
MGMT_EV_AUTH_FAILED            = 0x0011
MGMT_EV_DEVICE_FOUND           = 0x0012
MGMT_EV_DISCOVERING            = 0x0013
MGMT_EV_DEVICE_BLOCKED         = 0x0014
MGMT_EV_DEVICE_UNBLOCKED       = 0x0015
MGMT_EV_DEVICE_UNPAIRED        = 0x0016
MGMT_EV_PASSKEY_NOTIFY         = 0x0017

# Settings returned by MGMT_OP_READ_INFO
MGMT_SETTING_POWERED           = 0x00000001
MGMT_SETTING_CONNECTABLE       = 0x00000002
MGMT_SETTING_FAST_CONNECTABLE  = 0x00000004
MGMT_SETTING_DISCOVERABLE      = 0x00000008
MGMT_SETTING_PAIRABLE          = 0x00000010
MGMT_SETTING_LINK_SECURITY     = 0x00000020
MGMT_SETTING_SSP               = 0x00000040
MGMT_SETTING_BREDR             = 0x00000080
MGMT_SETTING_HS                = 0x00000100
MGMT_SETTING_LE                = 0x00000200

# Disconnect reason returned in MGMT_EV_DEVICE_DISCONNECTED
MGMT_DEV_DISCONN_UNKNOWN       = 0x00
MGMT_DEV_DISCONN_TIMEOUT       = 0x01
MGMT_DEV_DISCONN_LOCAL_HOST    = 0x02
MGMT_DEV_DISCONN_REMOTE        = 0x03

# Flags returned in MGMT_EV_DEVICE_FOUND
MGMT_DEV_FOUND_CONFIRM_NAME    = 0x01
MGMT_DEV_FOUND_LEGACY_PAIRING  = 0x02


class BluetoothSocketError(Exception):
    """Error raised for general issues with BluetoothSocket."""
    pass

class BluetoothInvalidPacketError(Exception):
    """Error raised when an invalid packet is received from the socket."""
    pass

class BluetoothControllerError(Exception):
    """Error raised when the Controller Error event is received."""
    pass


class BluetoothSocket(btsocket.socket):
    """Bluetooth Socket.

    BluetoothSocket wraps the btsocket.socket() class, and thus the system
    socket.socket() class, to implement the necessary send and receive methods
    for the HCI Control and Monitor protocols (aka mgmt_ops) of the
    Linux Kernel.

    Instantiate either BluetoothControlSocket or BluetoothMonitorSocket rather
    than this class directly.

    See bluez/doc/mgmt_api.txt for details.

    """

    def __init__(self):
        super(BluetoothSocket, self).__init__(family=btsocket.AF_BLUETOOTH,
                                              type=socket.SOCK_RAW,
                                              proto=btsocket.BTPROTO_HCI)
        self.events = []


    def send_command(self, code, index, data=''):
        """Send a command to the socket.

        To send a command, wait for the reply event, and parse it use
        send_command_and_wait() instead.

        @param code: Command Code.
        @param index: Controller index, may be MGMT_INDEX_NONE.
        @param data: Parameters as bytearray or str (optional).

        """
        # Send the command to the kernel
        msg = struct.pack('<HHH', code, index, len(data)) + data

        length = self.send(msg)
        if length != len(msg):
            raise BluetoothSocketError('Short write on socket')


    def recv_event(self):
        """Receive a single event from the socket.

        The event data is not parsed; in the case of command complete events
        this means it includes both the data for the event and the response
        for the command.

        Use settimeout() to set whether this method will block if there is no
        data, return immediately or wait for a specific length of time before
        timing out and raising TimeoutError.

        @return tuple of (event, index, data)

        """
        # Read the message from the socket
        hdr = bytearray(MGMT_HDR_SIZE)
        data = bytearray(512)
        (nbytes, ancdata, msg_flags, address) = self.recvmsg_into((hdr, data))
        if nbytes < MGMT_HDR_SIZE:
            raise BluetoothInvalidPacketError('Packet shorter than header')

        # Parse the header
        (event, index, length) = struct.unpack_from('<HHH', buffer(hdr))
        if nbytes < MGMT_HDR_SIZE + length:
            raise BluetoothInvalidPacketError('Packet shorter than length')

        return (event, index, data[:length])


    def send_command_and_wait(self, cmd_code, cmd_index, cmd_data='',
                              expected_length=None):
        """Send a command to the socket and wait for the reply.

        Additional events are appended to the events list of the socket object.

        @param cmd_code: Command Code.
        @param cmd_index: Controller index, may be btsocket.HCI_DEV_NONE.
        @param cmd_data: Parameters as bytearray or str.
        @param expected_length: May be set to verify the length of the data.

        Use settimeout() to set whether this method will block if there is no
        reply, return immediately or wait for a specific length of time before
        timing out and raising TimeoutError.

        @return tuple of (status, data)

        """
        self.send_command(cmd_code, cmd_index, cmd_data)

        while True:
            (event, index, data) = self.recv_event()

            if index != cmd_index:
                raise BluetoothInvalidPacketError(
                        ('Response for wrong controller index received: ' +
                         '0x%04d (expected 0x%04d)' % (index, cmd_index)))

            if event == MGMT_EV_CMD_COMPLETE:
                if len(data) < 3:
                    raise BluetoothInvalidPacketError(
                            ('Incorrect command complete event data length: ' +
                             '%d (expected at least 3)' % len(data)))

                (code, status) = struct.unpack_from('<HB', buffer(data, 0, 3))
                logging.debug('[0x%04x] command 0x%04x complete: 0x%02x',
                              index, code, status)

                if code != cmd_code:
                    raise BluetoothInvalidPacketError(
                            ('Response for wrong command code received: ' +
                             '0x%04d (expected 0x%04d)' % (code, cmd_code)))

                response_length = len(data) - 3
                if (expected_length is not None and
                    response_length != expected_length):
                    raise BluetoothInvalidPacketError(
                            ('Incorrect length of data for response: ' +
                             '%d (expected %d)' % (response_length,
                                                   expected_length)))

                return (status, data[3:])

            elif event == MGMT_EV_CMD_STATUS:
                if len(data) != 3:
                    raise BluetoothInvalidPacketError(
                            ('Incorrect command status event data length: ' +
                             '%d (expected 3)' % len(data)))

                (code, status) = struct.unpack_from('<HB', buffer(data, 0, 3))
                logging.debug('[0x%04x] command 0x%02x status: 0x%02x',
                              index, code, status)

                if code != cmd_code:
                    raise BluetoothInvalidPacketError(
                            ('Response for wrong command code received: ' +
                             '0x%04d (expected 0x%04d)' % (code, cmd_code)))

                return (status, None)

            elif event == MGMT_EV_CONTROLLER_ERROR:
                if len(data) != 1:
                    raise BluetoothInvalidPacketError(
                        ('Incorrect controller error event data length: ' +
                         '%d (expected 1)' % len(data)))

                (error_code) = struct.unpack_from('<B', buffer(data, 0, 1))

                raise BluetoothControllerError('Controller error: %d' %
                                               error_code)

            else:
                logging.debug('[0x%04x] event 0x%02x length: %d',
                              index, event, len(data))
                self.events.append((event, index, data))


class BluetoothControlSocket(BluetoothSocket):
    """Bluetooth Control Socket.

    BluetoothControlSocket provides convenient methods mapping to each mgmt_ops
    command that send an appropriately formatted command and parse the response.

    """

    DEFAULT_TIMEOUT = 15

    def __init__(self):
        super(BluetoothControlSocket, self).__init__()
        self.bind((btsocket.HCI_DEV_NONE, btsocket.HCI_CHANNEL_CONTROL))
        self.settimeout(self.DEFAULT_TIMEOUT)


    def read_version(self):
        """Read the version of the management interface.

        @return tuple (version, revision) on success, None on failure.

        """
        (status, data) = self.send_command_and_wait(
                MGMT_OP_READ_VERSION,
                MGMT_INDEX_NONE,
                expected_length=3)
        if status != MGMT_STATUS_SUCCESS:
            return None

        (version, revision) = struct.unpack_from('<BH', buffer(data))
        return (version, revision)


    def read_supported_commands(self):
        """Read the supported management commands and events.

        @return tuple (commands, events) on success, None on failure.

        """
        (status, data) = self.send_command_and_wait(
                MGMT_OP_READ_COMMANDS,
                MGMT_INDEX_NONE)
        if status != MGMT_STATUS_SUCCESS:
            return None
        if len(data) < 4:
            raise BluetoothInvalidPacketError(
                    ('Incorrect length of data for response: ' +
                     '%d (expected at least 4)' % len(data)))

        (ncommands, nevents) = struct.unpack_from('<HH', buffer(data, 0, 4))
        offset = 4
        expected_length = offset + (ncommands * 2) + (nevents * 2)
        if len(data) != expected_length:
            raise BluetoothInvalidPacketError(
                    ('Incorrect length of data for response: ' +
                     '%d (expected %d)' % (len(data), expected_length)))

        commands = []
        while len(commands) < ncommands:
            commands.extend(struct.unpack_from('<H', buffer(data, offset, 2)))
            offset += 2

        events = []
        while len(events) < nevents:
            events.extend(struct.unpack_from('<H', buffer(data, offset, 2)))
            offset += 2

        return (commands, events)


    def read_index_list(self):
        """Read the list of currently known controllers.

        @return array of controller indexes on success, None on failure.

        """
        (status, data) = self.send_command_and_wait(
                MGMT_OP_READ_INDEX_LIST,
                MGMT_INDEX_NONE)
        if status != MGMT_STATUS_SUCCESS:
            return None
        if len(data) < 2:
            raise BluetoothInvalidPacketError(
                    ('Incorrect length of data for response: ' +
                     '%d (expected at least 2)' % len(data)))

        (nindexes,) = struct.unpack_from('<H', buffer(data, 0, 2))
        offset = 2
        expected_length = offset + (nindexes * 2)
        if len(data) != expected_length:
            raise BluetoothInvalidPacketError(
                    ('Incorrect length of data for response: ' +
                     '%d (expected %d)' % (len(data), expected_length)))

        indexes = []
        while len(indexes) < nindexes:
            indexes.extend(struct.unpack_from('<H', buffer(data, offset, 2)))
            offset += 2

        return indexes


    def read_info(self, index):
        """Read the state and basic information of a controller.

        Address is returned as a string in upper-case hex to match the
        BlueZ property.

        @param index: Controller index.

        @return tuple (address, bluetooth_version, manufacturer,
                       supported_settings, current_settings,
                       class_of_device, name, short_name)

        """
        (status, data) = self.send_command_and_wait(
                MGMT_OP_READ_INFO,
                index,
                expected_length=280)
        if status != MGMT_STATUS_SUCCESS:
            return None

        (address, bluetooth_version, manufacturer,
         supported_settings, current_settings,
         class_of_device_lo, class_of_device_mid, class_of_device_hi,
         name, short_name) = struct.unpack_from(
                '<6sBHLL3B249s11s',
                buffer(data))

        return (
                ':'.join('%02X' % x
                         for x in reversed(struct.unpack('6B', address))),
                bluetooth_version,
                manufacturer,
                supported_settings,
                current_settings,
                (class_of_device_lo |(class_of_device_mid << 8) |
                        (class_of_device_hi << 16)),
                name.rstrip('\0'),
                short_name.rstrip('\0'))
