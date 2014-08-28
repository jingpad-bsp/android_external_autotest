# Copyright (c) 2013 The Chromium OS Authors. All rights reserved.
# Use of this source code is governed by a BSD-style license that can be
# found in the LICENSE file.

"""The functionality in this class is used whenever one of the graphics_*
tests runs. It provides a sanity check on GPU failures and emits warnings
on recovered GPU hangs and errors on fallback to software rasterization.
"""

import glob, logging, os, sys

from autotest_lib.client.bin import utils
from autotest_lib.client.common_lib import error, test
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


class GraphicsKernelMemory(object):
    """
    Reads from sysfs to determine kernel gem objects and memory info.
    """
    # These are sysfs fields that will be read by this test.  For different
    # architectures, the sysfs field paths are different.  The "paths" are given
    # as lists of strings because the actual path may vary depending on the
    # system.  This test will read from the first sysfs path in the list that is
    # present.
    # e.g. ".../memory" vs ".../gpu_memory" -- if the system has either one of
    # these, the test will read from that path.

    exynos_fields = {
        'gem_objects' : ['/sys/kernel/debug/dri/0/exynos_gem_objects'],
        'memory'      : ['/sys/class/misc/mali0/device/memory',
                         '/sys/class/misc/mali0/device/gpu_memory'],
    }
    tegra_fields = {
        'memory': ['/sys/kernel/debug/memblock/memory'],
    }
    x86_fields = {
        'gem_objects' : ['/sys/kernel/debug/dri/0/i915_gem_objects'],
        'memory'      : ['/sys/kernel/debug/dri/0/i915_gem_gtt'],
    }
    arch_fields = {
        'exynos5' : exynos_fields,
        'tegra'   : tegra_fields,
        'i386'    : x86_fields,
        'x86_64'  : x86_fields,
    }

    num_errors = 0

    def get_memory_keyvals(self):
        """
        Reads the graphics memory values and returns them as keyvals.
        """
        keyvals = {}

        # Get architecture type and list of sysfs fields to read.
        arch = utils.get_cpu_soc_family()

        if not arch in self.arch_fields:
            raise error.TestFail('Architecture "%s" not yet supported.' % arch)
        fields = self.arch_fields[arch]

        for field_name in fields:
            possible_field_paths = fields[field_name]
            field_value = None
            for path in possible_field_paths:
                if utils.system('ls %s' % path):
                    continue
                field_value = utils.system_output('cat %s' % path)
                break

            if not field_value:
                logging.error('Unable to find any sysfs paths for field "%s"',
                              field_name)
                self.num_errors += 1
                continue

            parsed_results = self._parse_sysfs(field_value)

            for key in parsed_results:
                keyvals['%s_%s' % (field_name, key)] = parsed_results[key]

            if 'bytes' in parsed_results and parsed_results['bytes'] == 0:
                logging.error('%s reported 0 bytes', field_name)
                self.num_errors += 1

        keyvals['meminfo_MemUsed'] = (utils.read_from_meminfo('MemTotal') -
                                      utils.read_from_meminfo('MemFree'))
        keyvals['meminfo_SwapUsed'] = (utils.read_from_meminfo('SwapTotal') -
                                       utils.read_from_meminfo('SwapFree'))
        return keyvals

    def _parse_sysfs(self, output):
        """
        Parses output of graphics memory sysfs to determine the number of
        buffer objects and bytes.

        Arguments:
            output      Unprocessed sysfs output
        Return value:
            Dictionary containing integer values of number bytes and objects.
            They may have the keys 'bytes' and 'objects', respectively.  However
            the result may not contain both of these values.
        """
        results = {}
        labels = ['bytes', 'objects']

        for line in output.split('\n'):
            # Strip any commas to make parsing easier.
            line_words = line.replace(',', '').split()

            prev_word = None
            for word in line_words:
                # When a label has been found, the previous word should be the
                # value. e.g. "3200 bytes"
                if word in labels and word not in results and prev_word:
                    logging.info(prev_word)
                    results[word] = int(prev_word)

                prev_word = word

            # Once all values has been parsed, return.
            if len(results) == len(labels):
                return results

        return results


class GraphicsStateChecker(test.base_test):
    """
    Analyzes the state of the GPU and log history. Should be instantiated at the
    beginning of each graphics_* test.
    """
    crash_blacklist = []
    dirty_writeback_centisecs = 0
    existing_hangs = {}

    _BROWSER_VERSION_COMMAND = '/opt/google/chrome/chrome --version'
    _HANGCHECK = ['drm:i915_hangcheck_elapsed', 'drm:i915_hangcheck_hung']
    _MESSAGES_FILE = '/var/log/messages'

    def __init__(self, raise_error_on_hang=True):
        """
        Analyzes the initial state of the GPU and log history.
        """
        # Attempt flushing system logs every second instead of every 10 minutes.
        self.dirty_writeback_centisecs = utils.get_dirty_writeback_centisecs()
        utils.set_dirty_writeback_centisecs(100)
        self._raise_error_on_hang = raise_error_on_hang
        logging.info(utils.get_board_with_frequency_and_memory())
        self.GKM = GraphicsKernelMemory()

        if utils.get_cpu_arch() != 'arm':
            cmd = 'glxinfo | grep "OpenGL renderer string"'
            cmd = cros_ui.xcommand(cmd)
            output = utils.run(cmd)
            result = output.stdout.splitlines()[0]
            logging.info('glxinfo: %s', result)
            # TODO(ihf): Find exhaustive error conditions (especially ARM).
            if 'llvmpipe' in result.lower() or 'soft' in result.lower():
                raise error.TestFail('Refusing to run on SW rasterizer: ' +
                                     result)
            logging.info('Initialize: Checking for old GPU hangs...')
            f = open(self._MESSAGES_FILE, 'r')
            for line in f:
                for hang in self._HANGCHECK:
                    if hang in line:
                        logging.info(line)
                        self.existing_hangs[line] = line
            f.close()

    def finalize(self):
        """
        Analyzes the state of the GPU, log history and emits warnings or errors
        if the state changed since initialize. Also makes a note of the Chrome
        version for later usage in the perf-dashboard.
        """
        utils.set_dirty_writeback_centisecs(self.dirty_writeback_centisecs)
        new_gpu_hang = False
        if utils.get_cpu_arch() != 'arm':
            logging.info('Cleanup: Checking for new GPU hangs...')
            f = open(self._MESSAGES_FILE, 'r')
            for line in f:
                for hang in self._HANGCHECK:
                    if hang in line:
                        if not line in self.existing_hangs.keys():
                            logging.info(line)
                            logging.warning('Saw GPU hang during test.')
                            new_gpu_hang = True
            f.close()

            cmd = 'glxinfo | grep "OpenGL renderer string"'
            cmd = cros_ui.xcommand(cmd)
            output = utils.run(cmd)
            result = output.stdout.splitlines()[0]
            logging.info('glxinfo: %s', result)
            # TODO(ihf): Find exhaustive error conditions (especially ARM).
            if 'llvmpipe' in result.lower() or 'soft' in result.lower():
                logging.warning('Finished test on SW rasterizer.')
                raise error.TestFail('Finished test on SW rasterizer: ' +
                                     result)

            if self._raise_error_on_hang and new_gpu_hang:
                raise error.TestFail('Detected GPU hang during test.')

    def get_memory_access_errors(self):
        return self.GKM.num_errors

    def get_memory_keyvals(self):
        return self.GKM.get_memory_keyvals()
