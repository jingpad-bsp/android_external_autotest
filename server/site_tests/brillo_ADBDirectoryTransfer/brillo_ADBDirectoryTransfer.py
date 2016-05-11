# Copyright 2016 The Chromium OS Authors. All rights reserved.
# Use of this source code is governed by a BSD-style license that can be
# found in the LICENSE file.

import filecmp
import os
import shutil
import tempfile

from autotest_lib.client.common_lib import error
from autotest_lib.server import test


_DATA_STR_A = 'Alluminum, linoleum, magnesium, petrolium.'
_DATA_STR_B = ('A basket of biscuits, a basket of mixed biscuits,'
               'and a biscuit mixer.')


class brillo_ADBDirectoryTransfer(test.test):
    """Verify that ADB directory transfers work."""
    version = 1


    def setup(self):
        self.temp_dir = tempfile.mkdtemp()
        self.temp_dir_return = tempfile.mkdtemp()
        self.file_a = os.path.join(self.temp_dir, 'file_a')
        self.file_b = os.path.join(self.temp_dir, 'file_b')

        with open(self.file_a, 'w') as f:
            f.write(_DATA_STR_A)

        with open(self.file_b, 'w') as f:
            f.write(_DATA_STR_B)


    def run_once(self, host=None):
        """Body of the test."""
        device_temp_dir = os.path.join(host.get_tmp_dir(), 'adb_test_dir')
        return_temp_dir = os.path.join(self.temp_dir_return, 'adb_test_return')
        return_file_a = os.path.join(return_temp_dir, 'file_a')
        return_file_b = os.path.join(return_temp_dir, 'file_b')

        host.send_file(self.temp_dir, device_temp_dir, delete_dest=True)
        host.get_file(device_temp_dir, return_temp_dir, delete_dest=True)

        if not filecmp.cmp(self.file_a, return_file_a, shallow=False) or \
           not filecmp.cmp(self.file_b, return_file_b, shallow=False):
            raise error.TestFail('One of the files changed in transit')


    def cleanup(self):
        shutil.rmtree(self.temp_dir)
        shutil.rmtree(self.temp_dir_return)
