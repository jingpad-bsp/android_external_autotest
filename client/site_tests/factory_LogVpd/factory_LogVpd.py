# Copyright (c) 2010 The Chromium OS Authors. All rights reserved.
# Use of this source code is governed by a BSD-style license that can be
# found in the LICENSE file.

import gzip
import pprint
import subprocess
import sys
import StringIO
from autotest_lib.client.bin import factory
from autotest_lib.client.bin import test, utils
from autotest_lib.client.common_lib import error
from autotest_lib.client.common_lib import flashrom_util


class factory_LogVpd(test.test):
    version = 1

    def blob_to_gzipped_hex(self, blob_data):
        """ Compresses a blob and return as hex string  """
        blob = StringIO.StringIO()
        gzblob = gzip.GzipFile(fileobj=blob, mode='w')
        gzblob.write(blob_data)
        gzblob.close()
        blob.seek(0)
        return blob.read().encode('hex')

    def log_vpds(self):
        valid_vpds = 0
        vpd_sections = ['RO_VPD', 'RW_VPD']
        flashrom = flashrom_util.FlashromUtility()
        flashrom.initialize(flashrom.TARGET_BIOS)
        for vpd in vpd_sections:
            if vpd not in flashrom.layout:
                continue
            vpd_hex = self.blob_to_gzipped_hex(flashrom.read_section(vpd))
            factory.log("VPD Data: %s (gzipped hex): %s" % (vpd, vpd_hex))
            valid_vpds = valid_vpds + 1

        # Try to print by tool(mosys) if possible
        tool_report = utils.system_output("mosys -k vpd print all",
                                          ignore_status=True)
        # make the report only one line
        tool_report = ' '.join(tool_report.split('\n')).strip()
        if tool_report:
            factory.log('VPD Data (key-value): ' + tool_report)

        # we need at least one VPD to success.
        return valid_vpds > 0

    def run_once(self):
        if not self.log_vpds():
            raise error.TestFail('Cannot find any Vendor Product Data (VPD.')
