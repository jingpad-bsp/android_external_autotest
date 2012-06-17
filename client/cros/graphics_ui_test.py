# Copyright (c) 2012 The Chromium OS Authors. All rights reserved.
# Use of this source code is governed by a BSD-style license that can be
# found in the LICENSE file.

"""The functionality in this class is used whenever one of the graphics_*
tests runs. It provides a sanity check on GPU failures and emits warnings
on recovered GPU hangs and errors on fallback to software rasterization.
"""

import logging, re

import cros_ui, cros_ui_test
from autotest_lib.client.bin import utils
from autotest_lib.client.common_lib import error

class GraphicsUITest(cros_ui_test.UITest):
    """Base class for tests requiring graphics acceleration.

    How to derive from this class:
        - Do not override any methods in this class
    """
    version = 1

    hangs = {}

    _BROWSER_VERSION_COMMAND = '/opt/google/chrome/chrome --version'
    _HANGCHECK = 'drm:i915_hangcheck_elapsed'
    _MESSAGES_FILE = '/var/log/messages'

    def initialize(self, creds=None, is_creating_owner=False,
                   extra_chrome_flags=[], subtract_extra_chrome_flags=[]):
        """Analyzes the state of the GPU and log history."""
        if utils.get_cpu_arch() != 'arm':
          cmd = 'glxinfo | grep "OpenGL renderer string"'
          cmd = cros_ui.xcommand(cmd)
          output = utils.run(cmd)
          result = output.stdout.splitlines()[0]
          logging.info('glxinfo: %s', result)
          # TODO(ihf): Find exhaustive error conditions (especially ARM).
          if 'llvmpipe' in result.lower() or 'soft' in result.lower():
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
        """Analyzes the state of the GPU, log history and emits warnings or
        errors if the state changed since initialize. Also makes a note of the
        Chrome version for later usage in the perf-dashboard.
        """
        if utils.get_cpu_arch() != 'arm':
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
          if 'llvmpipe' in result.lower() or 'soft' in result.lower():
            logging.info('Finished test on SW rasterizer.')
            raise error.TestFail('Finished test on SW rasterizer: ' + result)

        # Graphics tests really care about the Chrome version installed.
        output = utils.run(self._BROWSER_VERSION_COMMAND)
        logging.info(output.stdout)
        prog = re.compile('(Chrome|Chromium) (\d+)\.(\d+)\.(\d+)\.(\d+)')
        m = prog.findall(output.stdout)
        if len(m) > 0:
            version = (int(m[0][1]), int(m[0][2]), int(m[0][3]), int(m[0][4]))
            keyvals = {}
            # Microsoft naming convention (Major, Minor, Build, Revision).
            keyvals['Google_Chrome_Version0'] = version[0]
            keyvals['Google_Chrome_Version1'] = version[1]
            keyvals['Google_Chrome_Version2'] = version[2]
            keyvals['Google_Chrome_Version3'] = version[3]
            self.write_perf_keyval(keyvals)
            logging.info('Found %s %d.%d.%d.%d.', m[0][0], version[0],
                version[1], version[2], version[3])

        cros_ui_test.UITest.cleanup(self)
