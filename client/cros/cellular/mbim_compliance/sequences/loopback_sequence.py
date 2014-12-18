# Copyright 2015 The Chromium OS Authors. All rights reserved.
# Use of this source code is governed by a BSD-style license that can be
# found in the LICENSE file.
"""
Loopback NTB-16/32 Sequence

Reference:
    [1] Universal Serial Bus Communication Class MBIM Compliance Testing: 20
        http://www.usb.org/developers/docs/devclass_docs/MBIM-Compliance-1.0.pdf
"""
import array

import common
from autotest_lib.client.cros.cellular.mbim_compliance import mbim_data_transfer
from autotest_lib.client.cros.cellular.mbim_compliance.sequences \
        import sequence

class LoopbackSequence(sequence.Sequence):
    """
    Data loopback sequence used for data transfer testing.

    In this sequence, we send out an IPv4 ping packet to the device which is
    in |connected| state and fetch the repsonse packet received from the device.

    """
    # Payload to be used for our test. This is an IPv4 ICMP ping packet
    DATA_PAYLOAD = [array.array('B', [0x45, 0x00, 0x00, 0x46, 0x00, 0x00,
                                      0x00, 0x00, 0x00, 0x01, 0xBC, 0xB4,
                                      0x7F, 0x00, 0x00, 0x01, 0x7F, 0x00,
                                      0x00, 0x02, 0x00, 0x00, 0x00, 0x00,
                                      0x00, 0x00, 0x00, 0x01, 0x61, 0x62,
                                      0x63, 0x64, 0x65, 0x66, 0x67, 0x68,
                                      0x69, 0x6A, 0x6B, 0x6C, 0x6D, 0x6E,
                                      0x6F, 0x70, 0x71, 0x72, 0x73, 0x74,
                                      0x75, 0x76, 0x77, 0x61, 0x62, 0x63,
                                      0x64, 0x65, 0x66, 0x67, 0x68, 0x69])]


    def run_internal(self, ntb_format):
        """
        Run the MBIM Loopback Sequence.

        Need to run the |connect| sequence before invoking this loopback
        sequence.

        @param ntb_format: Whether to send/receive an NTB16 or NTB32 frame.
                Possible values: NTB_FORMAT_16, NTB_FORMAT_32 (mbim_constants)
        @returns tuple of (nth, ndp, ndp_entries, payload) where,
                nth - NTH header object received.
                ndp - NDP header object received.
                ndp_entries - Array of NDP entry header objects.
                payload - Array of packets where each packet is a byte array.

        """
        # Step 1 is to run |connect| sequence which is expected to be run
        # before calling this to avoid calling sequences within another
        # sequence.

        # Step 2
        data_transfer = mbim_data_transfer.MBIMDataTransfer(self.device_context)
        data_transfer.send_data_packets(ntb_format, self.DATA_PAYLOAD)

        # Step 3
        nth, ndp, ndp_entries, payload = data_transfer.receive_data_packets(
                ntb_format)

        return (nth, ndp, ndp_entries, payload)
