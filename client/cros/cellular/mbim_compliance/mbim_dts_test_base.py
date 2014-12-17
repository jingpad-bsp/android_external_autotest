# Copyright (c) 2014 The Chromium OS Authors. All rights reserved.
# Use of this source code is governed by a BSD-style license that can be
# found in the LICENSE file.

import common
from autotest_lib.client.cros.cellular.mbim_compliance import mbim_test_base
from autotest_lib.client.cros.cellular.mbim_compliance.sequences \
        import connect_sequence
from autotest_lib.client.cros.cellular.mbim_compliance.sequences \
        import get_descriptors_sequence
from autotest_lib.client.cros.cellular.mbim_compliance.sequences \
        import mbim_open_generic_sequence


class MbimDtsTestBase(mbim_test_base.MbimTestBase):
    """ Base class for all the data transfer tests. """

    def run_precondition(self, ntb_format):
        """
        Runs all the precondition sequences for data transfer tests.

        @param ntb_format: Whether to send/receive an NTB16 or NTB32 frame.
                Possible values: NTB_FORMAT_16, NTB_FORMAT_32 (mbim_constants)
        @returns tuple of (desc_sequence, open_sequence, connect_sequence) where,
                desc_sequence - Handle to run the get descriptor sequence.
                open_sequence - Handle to run the open sequence.
                connect_sequence - Handle to run the connect sequence.

        """
        desc_sequence = get_descriptors_sequence.GetDescriptorsSequence(
                self.device_context)
        descriptors = desc_sequence.run()
        self.device_context.update_descriptor_cache(descriptors)
        open_sequence = mbim_open_generic_sequence.MBIMOpenGenericSequence(
                self.device_context)
        open_sequence.run(ntb_format=ntb_format)
        connect_seq = connect_sequence.ConnectSequence(self.device_context)
        connect_seq.run()

        return (desc_sequence, open_sequence, connect_seq)
