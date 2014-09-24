# Copyright (c) 2013 The Chromium OS Authors. All rights reserved.
# Use of this source code is governed by a BSD-style license that can be
# found in the LICENSE file.

"""
Provides graphics related utils, like capturing screenshots or checking on
the state of the graphics driver.
"""

import glob, logging, os, re, sys

from autotest_lib.client.bin import utils
from autotest_lib.client.common_lib import error
from autotest_lib.client.cros.graphics import drm


def xcommand(cmd, user=None):
    """
    Add the necessary X setup to a shell command that needs to connect to the X
    server.
    @param cmd: the command line string
    @param user: if not None su command to desired user.
    @return a modified command line string with necessary X setup
    """
    if utils.is_freon():
        raise error.TestFail('freon: xcommand is deprecated') 
    logging.warning("xcommand will be deprecated under freon!")
    if user is None:
        return 'DISPLAY=:0 XAUTHORITY=/home/chronos/.Xauthority ' + cmd
    return 'DISPLAY=:0 XAUTHORITY=/home/chronos/.Xauthority su %s -c \'%s\'' % (
                                                                      user, cmd)


def xsystem(cmd, user=None, timeout=None, ignore_status=False):
    """
    Run the command cmd, using utils.system, after adding the necessary
    setup to connect to the X server.

    @param cmd: The command.
    @param user: The user to switch to, or None for the current user.
    @param timeout: Optional timeout.
    @param ignore_status: Whether to check the return code of the command.
    """
    return utils.system(xcommand(cmd, user), timeout=timeout,
                        ignore_status=ignore_status)


def press_key(key_str):
    """Presses the given key(s).
    @param key_str: A string of the key(s), like 'ctrl+F4', 'Up'.
    """
    if utils.is_freon():
        raise error.TestFail('freon: press_key not implemented')
    command = 'xdotool key %s' % key_str
    xsystem(command)


XSET = 'LD_LIBRARY_PATH=/usr/local/lib xset'

def do_power_consumption_xset():
    """ Called from power_Consumption to immediately disable energy saving. """
    if utils.is_freon():
        raise error.TestFail('freon: do_power_consumption_xset not implemented')
    # Disable X screen saver
    xsystem(XSET + ' s 0 0')
    # Disable DPMS Standby/Suspend/Off
    xsystem(XSET + ' dpms 0 0 0')
    # Force monitor on
    xsystem(XSET + ' dpms force on')
    # Save off X settings
    xsystem(XSET + ' q')


def do_power_backlight_xset():
    """ Called from power_Backlight to disable screen blanking. """
    if utils.is_freon():
        raise error.TestFail('freon: do_power_backlight_xset not implemented')
    xsystem(XSET + ' s off')
    xsystem(XSET + ' dpms 0 0 0')
    xsystem(XSET + ' -dpms')


def wakeup_screen():
    """Wake up the screen if it is dark."""
    # Move the mouse a little bit to wake up the screen.
    xsystem('xdotool mousemove_relative 1 1')


def switch_screen_on(on):
    """
    Turn the touch screen on/off.

    @param on: On or off.
    """
    if on:
        xsystem(XSET + ' dpms force on')
    else:
        xsystem(XSET + ' dpms force off')


def take_screenshot(resultsdir, fname_prefix, extension='png'):
    """Take screenshot and save to a new file in the results dir.
    Args:
      @param resultsdir:   Directory to store the output in.
      @param fname_prefix: Prefix for the output fname.
      @param extension:    String indicating file format ('png', 'jpg', etc).
    Returns:
      the path of the saved screenshot file
    """

    old_exc_type = sys.exc_info()[0]

    next_index = len(glob.glob(
        os.path.join(resultsdir, '%s-*.%s' % (fname_prefix, extension))))
    screenshot_file = os.path.join(
        resultsdir, '%s-%d.%s' % (fname_prefix, next_index, extension))
    logging.info('Saving screenshot to %s.', screenshot_file)

    try:
        if utils.is_freon():
            image = drm.screenshot()
            image.save(screenshot_file)
            return screenshot_file
        else:
            xsystem('/usr/local/bin/import -window root -depth 8 %s' %
                    screenshot_file)
    except Exception as err:
        # Do not raise an exception if the screenshot fails while processing
        # another exception.
        if old_exc_type is None:
            raise
        logging.error(err)

    return screenshot_file


def take_screenshot_crop_by_height(fullpath, final_height, x_offset_pixels,
                                   y_offset_pixels):
    """
    Take a screenshot, crop to final height starting at given (x, y) coordinate.
    Image width will be adjusted to maintain original aspect ratio).

    @param fullpath: path, fullpath of the file that will become the image file.
    @param final_height: integer, height in pixels of resulting image.
    @param x_offset_pixels: integer, number of pixels from left margin
                            to begin cropping.
    @param y_offset_pixels: integer, number of pixels from top margin
                            to begin cropping.
    """
    if utils.is_freon():
        image = drm.screenshot()
        image.crop()
        width, height = image.size
        # Preserve aspect ratio: Wf / Wi == Hf / Hi
        final_width = int(width * (float(final_height) / height))
        box = (x_offset_pixels, y_offset_pixels,
               x_offset_pixels + final_width, y_offset_pixels + final_height)
        cropped = image.crop(box)
        cropped.save(fullpath)
        return fullpath

    params = {'height': final_height, 'x_offset': x_offset_pixels,
              'y_offset': y_offset_pixels, 'path': fullpath}
    import_cmd = ('/usr/local/bin/import -window root -depth 8 -crop '
                  'x%(height)d+%(x_offset)d+%(y_offset)d %(path)s' % params)

    execute_screenshot_capture(import_cmd)
    return fullpath


def take_screenshot_crop(fullpath, box=None):
    """
    Take a screenshot using import tool, crop according to dim given by the box.
    @param fullpath: path, full path to save the image to.
    @param box: 4-tuple giving the upper left and lower right pixel coordinates.
    """

    if utils.is_freon():
        image = drm.screenshot()
        if box:
            image = image.crop(box)
        image.save(fullpath)
        return fullpath

    if box:
        upperx, uppery, lowerx, lowery = box
        img_w = lowerx - upperx
        img_h = lowery - uppery
        import_cmd = ('/usr/local/bin/import -window root -depth 8 -crop '
                      '%dx%d+%d+%d' % (img_w, img_h, upperx, uppery))
    else:
        import_cmd = ('/usr/local/bin/import -window root -depth 8')

    execute_screenshot_capture('%s %s' % (import_cmd, fullpath))


def _get_display_resolution_freon():
    """
    Parses output of modetest to determine the display resolution of the dut.
    @return: tuple, (w,h) resolution of device under test.
    """
    modetest_output = utils.system_output('modetest -c')
    modetest_connector_pattern = (r'\d+\s+\d+\s+(connected|disconnected)\s+'
                                  r'[- 0-9a-zA-Z]+\s+\d+x\d+\s+\d+\s+\d+')
    modetest_mode_pattern = (r'\s+.+\d+\s+(\d+)\s+\d+\s+\d+\s+\d+\s+(\d+)\s+'
                             r'\d+\s+\d+\s+\d+\s+flags:')
    connected = False
    for line in modetest_output.splitlines():
        connector_match = re.match(modetest_connector_pattern, line)
        if connector_match is not None:
            if connector_match.group(1) == 'connected':
                connected = True
        if connected:
            mode_match = re.match(modetest_mode_pattern, line)
            if mode_match is not None:
                return int(mode_match.group(1)), int(mode_match.group(2))
    return None


def _get_display_resolution_x():
    """
    Parses output of xrandr to determine the display resolution of the dut.
    @return: tuple, (w,h) resolution of device under test.
    """
    env_vars = 'DISPLAY=:0.0 XAUTHORITY=/home/chronos/.Xauthority'
    cmd = '%s xrandr | egrep -o "current [0-9]* x [0-9]*"' % env_vars
    output = utils.system_output(cmd)
    match = re.search('(\d+) x (\d+)', output)
    if len(match.groups()) == 2:
        return int(match.group(1)), int(match.group(2))
    return None


def get_display_resolution():
    """
    Determines the display resolution of the dut.
    @return: tuple, (w,h) resolution of device under test.
    """
    if utils.is_freon():
        return _get_display_resolution_freon()
    else:
        return _get_display_resolution_x()


def call_xrandr(args_string=''):
    """
    Calls xrandr with the args given by args_string.

    e.g. call_xrandr('--output LVDS1 --off') will invoke:
        'xrandr --output LVDS1 --off'

    @param args_string: A single string containing all arguments.

    Return value: Output of xrandr
    """
    return utils.system_output(xcommand('xrandr %s' % args_string))


def get_xrandr_output_state():
    """
    Retrieves output status of connected display(s) using xrandr.

    When xrandr report a display is "connected", it doesn't mean the
    display is active. For active display, it will have '*' after display mode.

    Return value: dictionary of connected display states.
                  key = output name
                  value = True if the display is active; False otherwise.
    """
    output = call_xrandr().split('\n')
    xrandr_outputs = {}
    current_output_name = ''

    # Parse output of xrandr, line by line.
    for line in output:
        if line.startswith('Screen'):
            continue
        # If the line contains "connected", it is a connected display, as
        # opposed to a disconnected output.
        if line.find(' connected') != -1:
            current_output_name = line.split()[0]
            # Temporarily mark it as inactive until we see a '*' afterward.
            xrandr_outputs[current_output_name] = False
            continue

        # If "connected" was not found, this is a line that shows a display
        # mode, e.g:    1920x1080      50.0     60.0     24.0
        # Check if this has an asterisk indicating it's on.
        if line.find('*') != -1 and current_output_name:
            xrandr_outputs[current_output_name] = True
            # Reset the output name since this should not be set more than once.
            current_output_name = ''

    return xrandr_outputs


def set_xrandr_output(output_name, enable):
    """
    Sets the output given by |output_name| on or off.

    Parameters:
        output_name       name of output, e.g. 'HDMI1', 'LVDS1', 'DP1'
        enable            True or False, indicating whether to turn on or off
    """
    call_xrandr('--output %s --%s' % (output_name, 'auto' if enable else 'off'))


def get_external_connector_name():
    """Gets the name of the external output connector.

    @return The external output connector name as a string, if any.
            Otherwise, return False.
    """
    if utils.is_freon():
        raise error.TestFail('freon: get_external_connector_name '
                             'not implemented')
    xrandr_output = get_xrandr_output_state()
    for output in xrandr_output.iterkeys():
        if (output.startswith('HDMI') or
            output.startswith('DP') or
            output.startswith('DVI')):
            return output
    return False


def get_internal_connector_name():
    """Gets the name of the internal output connector.

    @return The internal output connector name as a string, if any.
            Otherwise, return False.
    """
    if utils.is_freon():
        raise error.TestFail('freon: get_internal_connector_name '
                             'not implemented')
    xrandr_output = get_xrandr_output_state()
    for output in xrandr_output.iterkeys():
        # reference: chromium_org/chromeos/display/output_util.cc
        if (output.startswith('eDP') or
            output.startswith('LVDS') or
            output.startswith('DSI')):
            return output
    return False


def wait_output_connected(output):
    """Wait for output to connect.

    @param output: The output name as a string.

    @return: True if output is connected; False otherwise.
    """
    def _is_connected(output):
        """Helper function."""
        xrandr_output = get_xrandr_output_state()
        if output not in xrandr_output:
            return False
        return xrandr_output[output]

    if utils.is_freon():
        raise error.TestFail('freon: wait_output_connected not implemented')
    return utils.wait_for_value(lambda: _is_connected(output),
                                expected_value=True)


def execute_screenshot_capture(cmd):
    """
    Executes command to capture a screenshot.

    Provides safe execution of command to capture screenshot by wrapping
    the command around a try-catch construct.

    @param cmd: string, screenshot capture command.
    """
    if utils.is_freon():
        raise error.TestFail('freon: execute_screenshot_capture not '
                             'implemented')
    old_exc_type = sys.exc_info()[0]
    try:
        xsystem(cmd)
    except Exception as err:
        # Do not raise an exception if the screenshot fails while processing
        # another exception.
        if old_exc_type is None:
            raise
        logging.error(err)


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
    # TODO Add memory nodes once the GPU patches landed.
    rockchip_fields = {
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
        'rockchip': rockchip_fields,
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

            parsed_results = GraphicsKernelMemory._parse_sysfs(field_value)

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

    @staticmethod
    def _parse_sysfs(output):
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


class GraphicsStateChecker(object):
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
        self.graphics_kernel_memory = GraphicsKernelMemory()

        if utils.get_cpu_arch() != 'arm':
            # TODO(ihf): Freonize glxinfo (crbug.com/422167).
            if not utils.is_freon():
                cmd = 'glxinfo | grep "OpenGL renderer string"'
                cmd = xcommand(cmd)
                output = utils.run(cmd)
                result = output.stdout.splitlines()[0]
                logging.info('glxinfo: %s', result)
                # TODO(ihf): Find exhaustive error conditions (especially ARM).
                if 'llvmpipe' in result.lower() or 'soft' in result.lower():
                    raise error.TestFail('Refusing to run on SW rasterizer: ' +
                                         result)
            logging.info('Initialize: Checking for old GPU hangs...')
            messages = open(self._MESSAGES_FILE, 'r')
            for line in messages:
                for hang in self._HANGCHECK:
                    if hang in line:
                        logging.info(line)
                        self.existing_hangs[line] = line
            messages.close()

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
            messages = open(self._MESSAGES_FILE, 'r')
            for line in messages:
                for hang in self._HANGCHECK:
                    if hang in line:
                        if not line in self.existing_hangs.keys():
                            logging.info(line)
                            logging.warning('Saw GPU hang during test.')
                            new_gpu_hang = True
            messages.close()

            if not utils.is_freon():
                cmd = 'glxinfo | grep "OpenGL renderer string"'
                cmd = xcommand(cmd)
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
        """ Returns the number of errors while reading memory stats. """
        return self.graphics_kernel_memory.num_errors

    def get_memory_keyvals(self):
        """ Returns memory stats. """
        return self.graphics_kernel_memory.get_memory_keyvals()
