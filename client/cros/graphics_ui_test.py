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

    def initialize(self):
        cmd = 'glxinfo | grep renderer'
        cmd = cros_ui.xcommand(cmd)
        output = utils.run(cmd)
        result = output.stdout.splitlines()[0]
        logging.info('glxinfo: %s', result)
        if 'llvm' in result.lower() or 'softpipe' in result.lower():
          raise error.TestFail('Refusing to run on SW rasterizer: ' + result)
        if not 'intel' in result.lower():
          raise error.TestFail('Want to run on Intel HW rasterizer: ' + result)
        logging.info('Initialize: Checking for old GPU hangs...')
        f = open(self._MESSAGES_FILE, 'r')
        for line in f:
          if self._HANGCHECK in line:
            logging.info(line)
            self.hangs[line] = line

        cros_ui_test.UITest.initialize(self)

    def cleanup(self):
        cros_ui_test.UITest.cleanup(self)

        cmd = 'glxinfo | grep renderer'
        cmd = cros_ui.xcommand(cmd)
        output = utils.run(cmd)
        result = output.stdout.splitlines()[0]
        logging.info('glxinfo: %s', result)
        if 'llvm' in result.lower() or 'softpipe' in result.lower():
          raise error.TestFail('Finished test on SW rasterizer: ' + result)
        if not 'intel' in result.lower():
          raise error.TestFail('Finished test not on Intel HW rast: ' + result)
        logging.info('Cleanup: Checking for new GPU hangs...')
        f = open(self._MESSAGES_FILE, 'r')
        for line in f:
          if self._HANGCHECK in line:
            if not line in self.hangs.keys():
              logging.info(line)
              self.job.record('WARN', None, 'Saw GPU hang during test ', line)


