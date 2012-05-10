# Copyright (c) 2012 The Chromium OS Authors. All rights reserved.
# Use of this source code is governed by a BSD-style license that can be
# found in the LICENSE file.

import logging, os

import common, cros_ui, cros_ui_test
from autotest_lib.client.bin import utils
from autotest_lib.client.common_lib import error

class GraphicsUITest(cros_ui_test.UITest):
    """Base class for tests requiring graphics acceleration.

    How to derive from this class:
        - Do not override any methods in this class
    """
    version = 1

    hangs = {}

    _MESSAGES_FILE = '/var/log/messages'
    _HANGCHECK = 'drm:i915_hangcheck_elapsed'

    def initialize(self, creds=None, is_creating_owner=False,
                   extra_chrome_flags=[], subtract_extra_chrome_flags=[]):
        cmd = 'glxinfo | grep "OpenGL renderer string"'
        cmd = cros_ui.xcommand(cmd)
        output = utils.run(cmd)
        result = output.stdout.splitlines()[0]
        logging.info('glxinfo: %s', result)
        # TODO(ihf): Find exhaustive error conditions (especially ARM).
        if 'llvm' in result.lower() or 'soft' in result.lower():
          raise error.TestFail('Refusing to run on SW rasterizer: ' + result)
        logging.info('Initialize: Checking for old GPU hangs...')
        f = open(self._MESSAGES_FILE, 'r')
        for line in f:
          if self._HANGCHECK in line:
            logging.info(line)
            self.hangs[line] = line
        f.close()

        cros_ui_test.UITest.initialize(self, creds, is_creating_owner,
            extra_chrome_flags, subtract_extra_chrome_flags)

    def cleanup(self):
        logging.info('Cleanup: Checking for new GPU hangs...')
        f = open(self._MESSAGES_FILE, 'r')
        for line in f:
          if self._HANGCHECK in line:
            if not line in self.hangs.keys():
              logging.info(line)
              self.job.record('WARN', None, 'Saw GPU hang during test.')
        f.close()

        cmd = 'glxinfo | grep "OpenGL renderer string"'
        cmd = cros_ui.xcommand(cmd)
        output = utils.run(cmd)
        result = output.stdout.splitlines()[0]
        logging.info('glxinfo: %s', result)
        # TODO(ihf): Find exhaustive error conditions (especially ARM).
        if 'llvm' in result.lower() or 'soft' in result.lower():
          logging.info('Finished test on SW rasterizer.')
          raise error.TestFail('Finished test on SW rasterizer: ' + result)

        cros_ui_test.UITest.cleanup(self)
