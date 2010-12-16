# Copyright (c) 2010 The Chromium OS Authors. All rights reserved.
# Use of this source code is governed by a BSD-style license that can be
# found in the LICENSE file.

import glob, os

from autotest_lib.client.bin import test, utils
from autotest_lib.client.common_lib import error
from autotest_lib.client.common_lib import gbb_util


class factory_WriteGBB(test.test):
    version = 3

    def run_once(self, shared_dict={}):
        # More convenient to set the CWD to hardware_Components since a lot of
        # values in the component list are based on that directory.
        os.chdir(os.path.join(self.bindir, '../hardware_Components'))

        # If found the HwQual ID in shared_dict, identify the component files.
        if 'part_id_hwqual' in shared_dict:
            id = shared_dict['part_id_hwqual'].replace(' ', '_')
            component_file = 'data_*/components_%s' % id
        else:
            raise error.TestError(
                    'You need to run this test from factory UI, and have ' +
                    'successfully completed the HWQual-ID matching test ')

        component_files = glob.glob(component_file)
        if len(component_files) != 1:
            raise error.TestError(
                'Unable to find the component file: %s' % component_file)
        component_file = component_files[0]
        components = eval(utils.read_file(component_file))

        gbb = gbb_util.GBBUtility(temp_dir=self.resultsdir,
                                  keep_temp_files=True)
        gbb.set_bmpfv(utils.read_file(components['data_bitmap_fv'][0]))
        gbb.set_hwid(components['part_id_hwqual'][0])
        gbb.commit()
