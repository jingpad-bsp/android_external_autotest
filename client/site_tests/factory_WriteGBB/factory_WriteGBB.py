# Copyright (c) 2010 The Chromium OS Authors. All rights reserved.
# Use of this source code is governed by a BSD-style license that can be
# found in the LICENSE file.

import glob, os

from autotest_lib.client.bin import factory, test, utils
from autotest_lib.client.common_lib import error
from autotest_lib.client.cros import gooftools


class factory_WriteGBB(test.test):
    """ Updates system firmware GBB data with probed HWID information. """
    version = 4

    def run_once(self):
        # We trust previous execution result of HWQual ID probing test
        # (factory_ProbeHWID).
        # If the value was incorrect, it will be detected in the finalization
        # stage (factory_Finalize, gooftool --finalize => --verify_hwid).
        probed_hwid = factory.get_shared_data(factory.LAST_PROBED_HWID_NAME)
        if not probed_hwid:
            raise error.TestError(
                    'You need to run this test from factory UI, and have ' +
                    'successfully completed the HWQual-ID matching test ')
        gooftools.run('gooftool --write_gbb="%s" --verbose' % probed_hwid)
