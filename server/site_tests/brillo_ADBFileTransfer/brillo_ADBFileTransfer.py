# Copyright 2016 The Chromium OS Authors. All rights reserved.
# Use of this source code is governed by a BSD-style license that can be
# found in the LICENSE file.

import filecmp
import os
import tempfile

from autotest_lib.client.common_lib import error
from autotest_lib.server import test


_DATA_SIZE = 20 * 1000 * 1000
_DATA_STR = ''.join(chr(i) for i in range(256))
_DATA_STR *= (len(_DATA_STR) - 1 + _DATA_SIZE) / len(_DATA_STR)
_DATA_STR = _DATA_STR[:_DATA_SIZE]


class brillo_ADBFileTransfer(test.test):
    """Verify that ADB file transfers work."""
    version = 1


    def setup(self):
        self.temp_file = tempfile.NamedTemporaryFile()
        self.temp_file.write(_DATA_STR)


    def run_once(self, host=None):
        """Body of the test."""
        device_temp_file = os.path.join(host.get_tmp_dir(), 'adb_test_file')

        host.run('rm -rf %s' % device_temp_file)

        with tempfile.NamedTemporaryFile() as return_temp_file:
            host.adb_run('push %s %s' %
                    (self.temp_file.name, device_temp_file))
            host.adb_run('pull %s %s' %
                    (device_temp_file, return_temp_file.name))
            if not filecmp.cmp(self.temp_file.name, return_temp_file.name,
                               shallow=False):
                raise error.TestFail('Got back different file than we sent')

            with tempfile.NamedTemporaryFile() as cat_data:
                host.run('cat %s' % device_temp_file,
                             stdout=cat_data)
                if not filecmp.cmp(self.temp_file.name, cat_data.name,
                                   shallow=False):
                    raise error.TestFail(
                            'Cat did not return same contents we sent')


    def cleanup(self):
        self.temp_file.close()
