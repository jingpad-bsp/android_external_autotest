# Copyright 2016 The Chromium OS Authors. All rights reserved.
# Use of this source code is governed by a BSD-style license that can be
# found in the LICENSE file.

import logging
import os
import re

from autotest_lib.client.bin import utils
from autotest_lib.client.common_lib import error
from autotest_lib.client.common_lib.cros import arc

_SDCARD_EXEC = '/sdcard/gralloctest'
_EXEC_DIRECTORY = '/data/executables/'
_ANDROID_EXEC = _EXEC_DIRECTORY + 'gralloctest'


class graphics_Gralloc(arc.ArcTest):
    """gralloc test."""
    version = 1

    def setup(self):
        os.chdir(self.srcdir)
        utils.make('clean')
        utils.make('all')

    def initialize(self):
        super(graphics_Gralloc, self).initialize(autotest_ext=True)

    def arc_setup(self):
        super(graphics_Gralloc, self).arc_setup()
        # Get the executable from CrOS and copy it to Android container. Due to
        # weird permission issues inside the container, we first have to copy
        # the test to /sdcard/, then move it to a /data/ subdirectory we create.
        # The permissions on the exectuable have to be modified as well.
        arc.adb_root()
        cmd = os.path.join(self.srcdir, 'gralloctest')
        arc.adb_cmd('-e push %s %s' % (cmd, _SDCARD_EXEC))
        arc._android_shell('mkdir -p %s' % (_EXEC_DIRECTORY))
        arc._android_shell('mv %s %s' % (_SDCARD_EXEC, _ANDROID_EXEC))
        arc._android_shell('chmod o+rwx %s' % (_ANDROID_EXEC))

    def arc_teardown(self):
        # Remove test contents from Android container.
        arc._android_shell('rm -rf %s' % (_EXEC_DIRECTORY))
        super(graphics_Gralloc, self).arc_teardown()

    def run_once(self):
        failures = 0
        # TODO(ihf): shard this test into multiple control files.
        test_names = [
            'alloc_varying_sizes', 'alloc_usage', 'api', 'gralloc_order',
            'uninitialized_handle', 'freed_handle', 'mapping', 'perform',
            'ycbcr', 'async'
        ]

        # Run the tests and capture stdout.
        for test_name in test_names:
            stdout = arc._android_shell('%s %s' % (_ANDROID_EXEC, test_name))
            # Look for the regular expression indicating success.
            match = re.search(r'\[  PASSED  \]', stdout)
            if not match:
                failures += 1
                logging.error(stdout)
            else:
                logging.debug(stdout)

        if failures:
            raise error.TestFail('Failed: saw %d gralloc failures.' % failures)
