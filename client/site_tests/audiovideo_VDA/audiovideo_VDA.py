# Copyright (c) 2012 The Chromium Authors. All rights reserved.
# Use of this source code is governed by a BSD-style license that can be
# found in the LICENSE file.

import logging
import os
from autotest_lib.client.common_lib import error
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


    def run_once(self, videos):
        path = os.path.join(self.cr_source_dir, 'content', 'common',
                            'gpu', 'testdata', '')

        last_test_failure = None
        for video in videos:
            cmd_line = ('--test_video_data="%s%s"' % (path, video))

            try:
                self.run_chrome_binary_test(self.binary, cmd_line)
            except error.TestFail as test_failure:
                # Continue to run the remaining test videos and raise
                # the last failure after finishing all videos.
                logging.error('%s: %s', video, test_failure.message)
                last_test_failure = test_failure

        if last_test_failure:
            raise last_test_failure
