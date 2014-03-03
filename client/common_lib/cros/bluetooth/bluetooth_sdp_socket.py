# Copyright (c) 2013 The Chromium OS Authors. All rights reserved.
# Use of this source code is governed by a BSD-style license that can be
# found in the LICENSE file.

import socket
import struct

import btsocket

SDP_HDR_FORMAT        = '>BHH'
SDP_HDR_SIZE          = struct.calcsize(SDP_HDR_FORMAT)
SDP_TID_CNT           = 1 << 16
SDP_MAX_SSR_UUIDS_CNT = 12
SDP_BODY_CNT_FORMAT   = '>HH'
SDP_BODY_CNT_SIZE     = struct.calcsize(SDP_BODY_CNT_FORMAT)
BLUETOOTH_BASE_UUID   = 0x0000000000001000800000805F9B34FB

# Constants from lib/sdp.h in BlueZ source
SDP_RESPONSE_TIMEOUT    = 20
SDP_REQ_BUFFER_SIZE     = 2048
SDP_RSP_BUFFER_SIZE     = 65535
SDP_PDU_CHUNK_SIZE      = 1024

SDP_PSM                 = 0x0001

SDP_UUID                = 0x0001

SDP_DATA_NIL            = 0x00
SDP_UINT8               = 0x08
SDP_UINT16              = 0x09
SDP_UINT32              = 0x0A
SDP_UINT64              = 0x0B
SDP_UINT128             = 0x0C
SDP_INT8                = 0x10
SDP_INT16               = 0x11
SDP_INT32               = 0x12
SDP_INT64               = 0x13
SDP_INT128              = 0x14
SDP_UUID_UNSPEC         = 0x18
SDP_UUID16              = 0x19
SDP_UUID32              = 0x1A
SDP_UUID128             = 0x1C
SDP_TEXT_STR_UNSPEC     = 0x20
SDP_TEXT_STR8           = 0x25
SDP_TEXT_STR16          = 0x26
SDP_TEXT_STR32          = 0x27
SDP_BOOL                = 0x28
SDP_SEQ_UNSPEC          = 0x30
SDP_SEQ8                = 0x35
SDP_SEQ16               = 0x36
SDP_SEQ32               = 0x37
SDP_ALT_UNSPEC          = 0x38
SDP_ALT8                = 0x3D
SDP_ALT16               = 0x3E
SDP_ALT32               = 0x3F
SDP_URL_STR_UNSPEC      = 0x40
SDP_URL_STR8            = 0x45
SDP_URL_STR16           = 0x46
SDP_URL_STR32           = 0x47

SDP_ERROR_RSP           = 0x01
SDP_SVC_SEARCH_REQ      = 0x02
SDP_SVC_SEARCH_RSP      = 0x03
SDP_SVC_ATTR_REQ        = 0x04
SDP_SVC_ATTR_RSP        = 0x05
SDP_SVC_SEARCH_ATTR_REQ = 0x06
SDP_SVC_SEARCH_ATTR_RSP = 0x07


class BluetoothSDPSocketError(Exception):
    """Error raised for SDP-related issues with BluetoothSDPSocket."""
    pass


class BluetoothSDPSocket(btsocket.socket):
    """Bluetooth SDP Socket.

    BluetoothSDPSocket wraps the btsocket.socket() class to implement
    the necessary send and receive methods for the SDP protocol.

    """

    def __init__(self):
        super(BluetoothSDPSocket, self).__init__(family=btsocket.AF_BLUETOOTH,
                                                 type=socket.SOCK_SEQPACKET,
                                                 proto=btsocket.BTPROTO_L2CAP)
        self.tid = 0


    def gen_tid(self):
        """Generate new Transaction ID

        @return Transaction ID

        """
        self.tid = (self.tid + 1) % SDP_TID_CNT
        return self.tid


    def connect(self, address):
        """Connect to device with the given address

        @param address: Bluetooth address.

        """
        super(BluetoothSDPSocket, self).connect((address, SDP_PSM))


    def send_request(self, code, tid, data, forced_pdu_size=None):
        """Send a request to the socket.

        @param code: Request code.
        @param tid: Transaction ID.
        @param data: Parameters as bytearray or str.
        @param forced_pdu_size: Use certain PDU size parameter instead of
               calculating actual length of sequence.

        @raise BluetoothSDPSocketError: if 'send' to the socket didn't succeed.

        """
        size = len(data)
        if forced_pdu_size != None:
            size = forced_pdu_size
        msg = struct.pack(SDP_HDR_FORMAT, code, tid, size) + data

        length = self.send(msg)
        if length != len(msg):
            raise BluetoothSDPSocketError('Short write on socket')


    def recv_response(self):
        """Receive a single response from the socket.

        The response data is not parsed.

        Use settimeout() to set whether this method will block if there is no
        reply, return immediately or wait for a specific length of time before
        timing out and raising TimeoutError.

        @return tuple of (code, tid, data)
        @raise BluetoothSDPSocketError: if the received packet is too small or
               if size of the packet differs from size written in header

        """
        # Read the response from the socket
        response = self.recv(SDP_RSP_BUFFER_SIZE)

        if len(response) < SDP_HDR_SIZE:
            raise BluetoothSDPSocketError('Short read on socket')

        code, tid, length = struct.unpack_from(SDP_HDR_FORMAT, response)
        data = response[SDP_HDR_SIZE:]

        if length != len(data):
            raise BluetoothSDPSocketError('Short read on socket')

        return code, tid, data


    def send_request_and_wait(self, req_code, req_data, forced_pdu_size=None):
        """Send a request to the socket and wait for the response.

        The response data is not parsed.

        @param req_code: Request code.
        @param req_data: Parameters as bytearray or str.
        @param forced_pdu_size: Use certain PDU size parameter instead of
               calculating actual length of sequence.

        Use settimeout() to set whether this method will block if there is no
        reply, return immediately or wait for a specific length of time before
        timing out and raising TimeoutError.

        @return tuple of (rsp_code, data)
        @raise BluetoothSDPSocketError: if Transaction ID of the response
               doesn't match to Transaction ID sent in request

        """
        req_tid = self.gen_tid()
        self.send_request(req_code, req_tid, req_data, forced_pdu_size)
        rsp_code, rsp_tid, rsp_data = self.recv_response()

        if req_tid != rsp_tid:
            raise BluetoothSDPSocketError("Transaction IDs for request and "
                                          "response don't match")

        return rsp_code, rsp_data


    def _pack_uuids(self, uuids, preferred_size):
        """Pack a list of UUIDs to a binary sequence

        @param uuids: List of UUIDs (as integers).
        @param preferred_size: Preffered size of UUIDs in bits (16, 32, or 128).

        @return packed list as a str
        @raise BluetoothSDPSocketError: if list of UUIDs after packing is larger
               than or equal to 2^32 bytes or the given preferred size is not
               supported by SDP

        """
        if preferred_size not in (16, 32, 128):
            raise BluetoothSDPSocketError('Unsupported UUID size: %d; '
                                          'Supported values are: 16, 32, 128'
                                          % preferred_size)

        res = ''
        for uuid in uuids:
            # Fall back to 128 bits if the UUID does not fit into preferred_size
            if uuid >= (1 << preferred_size) or preferred_size == 128:
                uuid128 = uuid
                if uuid < (1 << 32):
                    uuid128 = (uuid128 << 96) + BLUETOOTH_BASE_UUID
                packed_uuid = struct.pack('>BQQ', SDP_UUID128, uuid128 >> 64,
                                          uuid128 & ((1 << 64) - 1))
            elif preferred_size == 16:
                packed_uuid = struct.pack('>BH', SDP_UUID16, uuid)
            elif preferred_size == 32:
                packed_uuid = struct.pack('>BI', SDP_UUID32, uuid)

            res += packed_uuid

        size = len(res)
        if size < (1 << 8):
            header = struct.pack('>BB', SDP_SEQ8, size)
        elif size < (1 << 16):
            header = struct.pack('>BH', SDP_SEQ16, size)
        elif size < (1 << 32):
            header = struct.pack('>BI', SDP_SEQ32, size)
        else:
            raise BluetoothSDPSocketError('List is too long')

        res = header + res

        return res


    def _unpack_uuids(self, response):
        """Unpack SDP response

        @param response: body of raw SDP response.

        @return tuple of (uuids, cont_state)

        """
        total_cnt, cur_cnt = struct.unpack_from(SDP_BODY_CNT_FORMAT, response)
        scanned = SDP_BODY_CNT_SIZE
        uuids = []
        for i in range(cur_cnt):
            uuid, = struct.unpack_from('>I', response, scanned)
            uuids.append(uuid)
            scanned += 4

        cont_state = response[scanned:]
        return uuids, cont_state


    def _unpack_error_code(self, response):
        """Unpack Error Code from SDP error response

        @param response: Body of raw SDP response.

        @return Error Code as int

        """
        error_code, = struct.unpack_from('>H', response)
        return error_code


    def service_search_request(self, uuids, max_rec_cnt, preferred_size=32,
                               forced_pdu_size=None, invalid_request=False):
        """Send a Service Search Request

        @param uuids: List of UUIDs (as integers) to look for.
        @param max_rec_cnt: Maximum count of returned service records.
        @param preferred_size: Preffered size of UUIDs in bits (16, 32, or 128).
        @param forced_pdu_size: Use certain PDU size parameter instead of
               calculating actual length of sequence.
        @param invalid_request: Whether to send request with intentionally
               invalid syntax for testing purposes (bool flag).

        @return list of found services' service record handles or Error Code
        @raise BluetoothSDPSocketError: arguments do not match the SDP
               restrictions or if the response has an incorrect code

        """
        if max_rec_cnt < 1 or max_rec_cnt > 0xFFFF:
            raise BluetoothSDPSocketError('MaximumServiceRecordCount must be '
                                          'between 1 and 0xFFFF, inclusive')

        if len(uuids) > SDP_MAX_SSR_UUIDS_CNT:
            raise BluetoothSDPSocketError('Too many UUIDs')

        pattern = self._pack_uuids(uuids, preferred_size) + struct.pack(
                  '>H', max_rec_cnt)
        cont_state = '\0'
        handles = []

        while True:
            request = pattern + cont_state

            # Request without any continuation state is an example of invalid
            # request syntax.
            if invalid_request:
                request = pattern

            code, response = self.send_request_and_wait(
                    SDP_SVC_SEARCH_REQ, request, forced_pdu_size)

            if code == SDP_ERROR_RSP:
                return self._unpack_error_code(response)

            if code != SDP_SVC_SEARCH_RSP:
                raise BluetoothSDPSocketError('Incorrect response code')

            cur_list, cont_state = self._unpack_uuids(response)
            handles.extend(cur_list)
            if cont_state == '\0':
                break

        return handles
