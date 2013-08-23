# Copyright (c) 2013 The Chromium OS Authors. All rights reserved.
# Use of this source code is governed by a BSD-style license that can be
# found in the LICENSE file.

"""The functionality in this class is used whenever one of the graphics_*
tests runs. It provides a sanity check on GPU failures and emits warnings
on recovered GPU hangs and errors on fallback to software rasterization.
"""

import glob, logging, os, sys

from autotest_lib.client.bin import utils
from autotest_lib.client.common_lib import error
from autotest_lib.client.cros import cros_ui

def take_screenshot(resultsdir, fname_prefix, format='png'):
  """Take screenshot and save to a new file in the results dir.

  Args:
    @param resultsdir:   Directory to store the output in.
    @param fname_prefix: Prefix for the output fname.
    @param format:       String indicating file format ('png', 'jpg', etc).

  Returns:
    the path of the saved screenshot file
  """
  next_index = len(glob.glob(
      os.path.join(resultsdir, '%s-*.%s' % (fname_prefix, format))))
  screenshot_file = os.path.join(
      resultsdir, '%s-%d.%s' % (fname_prefix, next_index, format))
  logging.info('Saving screenshot to %s.', screenshot_file)

  old_exc_type = sys.exc_info()[0]
  try:
      cros_ui.xsystem('/usr/local/bin/import -window root -depth 8 %s' %
              screenshot_file)
  except Exception as err:
      # Do not raise an exception if the screenshot fails while processing
      # another exception.
      if old_exc_type is None:
          raise
      logging.error(err)

  return screenshot_file


class GraphicsStateChecker(object):
    """Analyzes the state of the GPU and log history. Should be instantiated
    at the beginning of each graphics_* test.
    """
    hangs = {}
    crash_blacklist = []

    _BROWSER_VERSION_COMMAND = '/opt/google/chrome/chrome --version'
    _HANGCHECK = 'drm:i915_hangcheck_elapsed'
    _MESSAGES_FILE = '/var/log/messages'

    def __init__(self):
        """Analyzes the initial state of the GPU and log history.
        """
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

    def finalize(self):
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

        # TODO(ihf): Perform crash processing (primarily for Piglit) as is done
        # right now by ./client/cros/cros_ui_test.py and cros_logging.py.
