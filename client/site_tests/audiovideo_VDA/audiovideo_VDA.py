# Copyright (c) 2012 The Chromium Authors. All rights reserved.
# Use of this source code is governed by a BSD-style license that can be
# found in the LICENSE file.

import logging, os
from autotest_lib.client.bin import utils
from autotest_lib.client.cros import chrome_test

class audiovideo_VDA(chrome_test.ChromeBinaryTest):
  version = 1
  # Keep a current list of machines that don't support video acceleration.
  boards_without_VDA = ['x86-alex', 'x86-mario', 'x86-zgb']
  # Keep a current list of machines that use Exynos.
  boards_with_exynos_VDA = ['daisy', 'daisy_spring']

  def run_once(self):
    board = utils.get_board()
    if board in self.boards_without_VDA:
        logging.info('Found board known not to support video acceleration.')
        logging.info('Skip calling video_decode_accelerator_unittest.')
        return

    test_video_file = os.path.join(self.cr_source_dir, 'content', 'common',
                                   'gpu', 'testdata', 'test-25fps.h264')
    # The FPS expectations here are lower than observed in most runs to keep
    # the bots green.
    binary_test = 'video_decode_accelerator_unittest'
    cmd_line_params = ('--test_video_data="%s:320:240:250:258:35:150:1"' %
                       test_video_file)
    self.run_chrome_binary_test(binary_test, cmd_line_params)
    # Also run tests with EVDA for Exynos.
    if board in self.boards_with_exynos_VDA:
        cmd_line_params = ('%s --use-exynos-vda' % cmd_line_params)
        self.run_chrome_binary_test(binary_test, cmd_line_params)
