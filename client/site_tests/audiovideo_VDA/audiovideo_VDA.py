# Copyright (c) 2012 The Chromium Authors. All rights reserved.
# Use of this source code is governed by a BSD-style license that can be
# found in the LICENSE file.

import os
from autotest_lib.client.cros import chrome_test

SKIP_DEPS_ARG = 'skip_deps'

class audiovideo_VDA(chrome_test.ChromeBinaryTest):
    """
    This test is a wrapper of the chrome binary test:
    video_decode_accelerator_unittest.
    """

    version = 1
    binary = 'video_decode_accelerator_unittest'


    def initialize(self, arguments=[]):
        chrome_test.ChromeBinaryTest.initialize(
            self, nuke_browser_norestart=False,
            skip_deps=bool(SKIP_DEPS_ARG in arguments))


    def run_once(self, video_file, test_params):
        video_file = os.path.join(self.cr_source_dir, 'content', 'common',
                                  'gpu', 'testdata', video_file)

        cmd_line = ('--test_video_data="%s:%s"' % (video_file, test_params))
        self.run_chrome_binary_test(self.binary, cmd_line)
