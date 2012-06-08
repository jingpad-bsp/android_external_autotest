# Copyright (c) 2012 The Chromium OS Authors. All rights reserved.
# Use of this source code is governed by a BSD-style license that can be
# found in the LICENSE file.

"""
This is a profiler class for copying Profile-Guided-Optimization (PGO) data
files back to the host. When Chrome is built with -fprofile-generate, it dumps
its PGO data in a directory that this test copies back to test.profdir.

The PGO data is found where the build happens in the chroot, which is hardcoded
as the source_dir below.
"""

import logging
import os
import shutil
import tarfile
from autotest_lib.client.bin import profiler


class pgo(profiler.profiler):
    version = 1

    def initialize(self, source_dir='/tmp/pgo/chrome'):
        self._source_dir = source_dir


    def start(self, test):
        # Remove the .gcda files first.
        if os.path.exists(self._source_dir):
            shutil.rmtree(self._source_dir)


    def stop(self, test):
        if os.path.isdir(self._source_dir):
            tar = tarfile.open(name=os.path.join(test.profdir, 'pgo.tar.bz2'),
                               mode='w:bz2')
            tar.add(self._source_dir, arcname='chrome', recursive=True)
            tar.close()
        else:
            logging.error('PGO dir: %s not found', self._source_dir)
