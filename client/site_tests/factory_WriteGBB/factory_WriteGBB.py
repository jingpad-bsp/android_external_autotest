# Copyright (c) 2010 The Chromium OS Authors. All rights reserved.
# Use of this source code is governed by a BSD-style license that can be
# found in the LICENSE file.

import glob, os

from autotest_lib.client.bin import test, utils
from autotest_lib.client.common_lib import error
from autotest_lib.client.common_lib import flashrom_util


class factory_WriteGBB(test.test):
    version = 1

    def run_once(self, gbb_file):
        os.chdir(self.bindir)
        gbb_files = glob.glob(gbb_file)
        if len(gbb_files) > 1:
            raise error.TestError('More than one GBB file found')
        elif len(gbb_files) == 1:
            gbb_file = gbb_files[0]
        else:
            raise error.TestError('Unable to find GBB file: %s' % gbb_file)
        gbb_data = utils.read_file(gbb_file)

        flashrom = flashrom_util.FlashromUtility()
        flashrom.initialize(flashrom.TARGET_BIOS)

        gbb_section = 'FV_GBB'
        original_data = flashrom.read_section(gbb_section)
        # If no difference, no need to update.
        if gbb_data == original_data:
            return

        original_file = os.path.join(self.resultsdir, 'original_gbb.bin')
        utils.open_write_close(original_file, original_data)

        flashrom.write_section(gbb_section, gbb_data)
        flashrom.commit()
