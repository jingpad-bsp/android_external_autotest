# Copyright 2014 The Chromium OS Authors. All rights reserved.
# Use of this source code is governed by a BSD-style license that can be
# found in the LICENSE file.

import common
from autotest_lib.client.cros.cellular.mbim_compliance import mbim_constants
from autotest_lib.client.cros.cellular.mbim_compliance import mbim_errors
from autotest_lib.client.cros.cellular.mbim_compliance import mbim_test_base
from autotest_lib.client.cros.cellular.mbim_compliance.sequences \
        import connect_sequence
from autotest_lib.client.cros.cellular.mbim_compliance.sequences \
        import get_descriptors_sequence
from autotest_lib.client.cros.cellular.mbim_compliance.sequences \
        import loopback_sequence
from autotest_lib.client.cros.cellular.mbim_compliance.sequences \
        import mbim_open_generic_sequence


class network_MbimComplianceDTS01(mbim_test_base.MbimTestBase):
    """
    Validation for alternate setting 1 of the communication interface.

    This test validates data transfer operation for alternate setting 1 of the
    Communication Interface.

    Reference:
        [1] Universal Serial Bus Communication Class MBIM Compliance Testing: 28
        http://www.usb.org/developers/docs/devclass_docs/MBIM-Compliance-1.0.pdf

    """
    version = 1

    def run_internal(self):
        """ Run DTS_01 test. """
        # Precondition
        desc_sequence = get_descriptors_sequence.GetDescriptorsSequence(
                self.device_context)
        descriptors = desc_sequence.run()
        self.device_context.update_descriptor_cache(descriptors)
        open_sequence = mbim_open_generic_sequence.MBIMOpenGenericSequence(
                self.device_context)
        open_sequence.run(ntb_format=mbim_constants.NTB_FORMAT_16)
        connect = connect_sequence.ConnectSequence(self.device_context)
        connect.run()

        # Step 1
        loopback = loopback_sequence.LoopbackSequence(self.device_context)
        _, _, _, payload = loopback.run(
                ntb_format=self.device_context.ntb_format)

        # Step 2
        # Let's check the first byte of the first received payload to verify
        # that it is an IPv4 packet
        if payload[0][0] != 0x45:
            mbim_errors.log_and_raise(mbim_errors.MBIMComplianceAssertionError,
                                      'mbim1.0:3.2.1#5')
