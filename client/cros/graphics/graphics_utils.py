# Copyright (c) 2013 The Chromium OS Authors. All rights reserved.
# Use of this source code is governed by a BSD-style license that can be
# found in the LICENSE file.

"""
Provides graphics related utils, like capturing screenshots or checking on
the state of the graphics driver.
"""

import glob
import logging
import os
import re
import sys
import time
# Please limit the use of the uinput library to this file. Try not to spread
# dependencies and abstract as much as possible to make switching to a different
# input library in the future easier.
import uinput

from autotest_lib.client.bin import utils
from autotest_lib.client.common_lib import error
from autotest_lib.client.cros.graphics import drm


# TODO(ihf): Remove xcommand for non-freon builds.
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

# TODO(ihf): Remove xsystem for non-freon builds.
def xsystem(cmd, user=None):
    """
    Run the command cmd, using utils.system, after adding the necessary
    setup to connect to the X server.

    @param cmd: The command.
    @param user: The user to switch to, or None for the current user.
    @param timeout: Optional timeout.
    @param ignore_status: Whether to check the return code of the command.
    """
    return utils.system(xcommand(cmd, user))


# TODO(ihf): Remove XSET for non-freon builds.
XSET = 'LD_LIBRARY_PATH=/usr/local/lib xset'

def screen_disable_blanking():
    """ Called from power_Backlight to disable screen blanking. """
    if utils.is_freon():
        raise error.TestFail('freon: do_power_backlight_xset not implemented')
    xsystem(XSET + ' s off')
    xsystem(XSET + ' dpms 0 0 0')
    xsystem(XSET + ' -dpms')


def screen_disable_energy_saving():
    """ Called from power_Consumption to immediately disable energy saving. """
    if utils.is_freon():
        raise error.TestFail('freon: do_power_consumption_xset not implemented')
    # Disable X screen saver
    xsystem(XSET + ' s 0 0')
    # Disable DPMS Standby/Suspend/Off
    xsystem(XSET + ' dpms 0 0 0')
    # Force monitor on
    screen_switch_on(on=1)
    # Save off X settings
    xsystem(XSET + ' q')


def screen_switch_on(on):
    """Turn the touch screen on/off."""
    if on:
        xsystem(XSET + ' dpms force on')
    else:
        xsystem(XSET + ' dpms force off')


def screen_toggle_fullscreen():
    """Toggles fullscreen mode."""
    # TODO(ihf): Does this work on freon?
    if utils.is_freon():
        press_keys(['KEY_F11'])
    else:
        press_key_X('F11')


def screen_toggle_mirrored():
    """Toggles the mirrored screen."""
    # TODO(ihf): Does this work on freon?
    if utils.is_freon():
        press_keys(['KEY_LEFTCTRL', 'KEY_F4'])
    else:
        press_key_X('ctrl+F4')


def screen_wakeup():
    """Wake up the screen if it is dark."""
    # Move the mouse a little bit to wake up the screen.
    if utils.is_freon():
        _uinput_emit("REL_X", 1)
        _uinput_emit("REL_X", -1)
    else:
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


# Don't create a device during build_packages or for tests that don't need it.
uinput_device_keyboard = None
uinput_device_touch = None
uinput_device_mouse_rel = None

# Don't add more events to this list than are used. For a complete list of
# available events check python2.7/site-packages/uinput/ev.py.
UINPUT_DEVICE_EVENTS_KEYBOARD = [
        uinput.KEY_F4,
        uinput.KEY_F11,
        uinput.KEY_KPPLUS,
        uinput.KEY_KPMINUS,
        uinput.KEY_LEFTCTRL,
        uinput.KEY_TAB
    ]
# TODO(ihf): Find an ABS sequence that actually works.
UINPUT_DEVICE_EVENTS_TOUCH = [
        uinput.BTN_TOUCH,
        uinput.ABS_MT_SLOT,
        uinput.ABS_MT_POSITION_X + (0, 2560, 0, 0),
        uinput.ABS_MT_POSITION_Y + (0, 1700, 0, 0),
        uinput.ABS_MT_TRACKING_ID + (0, 10, 0, 0),
        uinput.BTN_TOUCH
]
UINPUT_DEVICE_EVENTS_MOUSE_REL = [
        uinput.REL_X,
        uinput.REL_Y,
        uinput.BTN_MOUSE,
        uinput.BTN_LEFT,
        uinput.BTN_RIGHT
    ]


def _get_uinput_device_keyboard():
    """
    Lazy initialize device and return it. We don't want to create a device during
    build_packages or for tests that don't need it, hence init is with = None.
    """
    global uinput_device_keyboard
    if uinput_device_keyboard is None:
        uinput_device_keyboard = uinput.Device(UINPUT_DEVICE_EVENTS_KEYBOARD)
    return uinput_device_keyboard


def _get_uinput_device_mouse_rel():
    """
    Lazy initialize device and return it. We don't want to create a device during
    build_packages or for tests that don't need it, hence init is with = None.
    """
    global uinput_device_mouse_rel
    if uinput_device_mouse_rel is None:
        uinput_device_mouse_rel = uinput.Device(UINPUT_DEVICE_EVENTS_MOUSE_REL)
    return uinput_device_mouse_rel


def _get_uinput_device_touch():
    """
    Lazy initialize device and return it. We don't want to create a device during
    build_packages or for tests that don't need it, hence init is with = None.
    """
    global uinput_device_touch
    if uinput_device_touch is None:
        uinput_device_touch = uinput.Device(UINPUT_DEVICE_EVENTS_TOUCH)
    return uinput_device_touch


def _uinput_translate_name(event_name):
    """
    Translates string |event_name| to uinput event.
    """
    return getattr(uinput, event_name)


def _uinput_emit(device, event_name, value, syn=True):
    """
    Wrapper for uinput.emit. Emits event with value.
    Example: ('REL_X', 20), ('BTN_RIGHT', 1)
    """
    event = _uinput_translate_name(event_name)
    device.emit(event, value, syn)


def _uinput_emit_click(device, event_name, syn=True):
    """
    Wrapper for uinput.emit_click. Emits click event. Only KEY and BTN events
    are accepted, otherwise ValueError is raised. Example: 'KEY_A'
    """
    event = _uinput_translate_name(event_name)
    device.emit_click(event, syn)


def _uinput_emit_combo(device, event_names, syn=True):
    """
    Wrapper for uinput.emit_combo. Emits sequence of events.
    Example: ['KEY_LEFTCTRL', 'KEY_LEFTALT', 'KEY_F5']
    """
    events = [_uinput_translate_name(en) for en in event_names]
    device.emit_combo(events, syn)


def press_keys(key_list):
    """Presses the given keys as one combination.

    Please do not leak uinput dependencies outside of the file.

    @param key: A list of key strings, e.g. ['LEFTCTRL', 'F4']
    """
    _uinput_emit_combo(_get_uinput_device_keyboard(), key_list)


# TODO(ihf): Remove press_key_X for non-freon builds.
def press_key_X(key_str):
    """Presses the given keys as one combination.
    @param key: A string of keys, e.g. 'ctrl+F4'.
    """
    if utils.is_freon():
        raise error.TestFail('freon: press_key_X not implemented')
    command = 'xdotool key %s' % key_str
    xsystem(command)


def click_mouse():
    """Just click the mouse.
    Presumably only hacky tests use this function.
    """
    logging.info('click_mouse()')
    # Move a little to make the cursor appear.
    device = _get_uinput_device_mouse_rel()
    _uinput_emit(device, 'REL_X', 1)
    # Some sleeping is needed otherwise events disappear.
    time.sleep(0.1)
    # Move cursor back to not drift.
    _uinput_emit(device, 'REL_X', -1)
    time.sleep(0.1)
    # Click down.
    _uinput_emit(device, 'BTN_LEFT', 1)
    time.sleep(0.2)
    # Release click.
    _uinput_emit(device, 'BTN_LEFT', 0)


# TODO(ihf): this function is broken. Make it work.
def activate_focus_at(rel_x, rel_y):
    """Clicks with the mouse at screen position (x, y).

    This is a pretty hacky method. Using this will probably lead to
    flaky tests as page layout changes over time.
    @param rel_x: relative horizontal position between 0 and 1.
    @param rel_y: relattive vertical position between 0 and 1.
    """
    width, height = get_display_resolution()
    device = _get_uinput_device_touch()
    _uinput_emit(device, 'ABS_MT_SLOT', 0, syn=False)
    _uinput_emit(device, 'ABS_MT_TRACKING_ID', 1, syn=False)
    _uinput_emit(device, 'ABS_MT_POSITION_X', int(rel_x*width), syn=False)
    _uinput_emit(device, 'ABS_MT_POSITION_Y', int(rel_y*height), syn=False)
    _uinput_emit(device, 'BTN_TOUCH', 1, syn=True)
    time.sleep(0.2)
    _uinput_emit(device, 'BTN_TOUCH', 0, syn=True)


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

def _get_num_outputs_freon():
    """
    Parses output of modetest to determine the number of connected displays
    @return: The number of connected displays
    """
    modetest_output = utils.system_output('modetest -c')
    modetest_connector_pattern = (r'\d+\s+\d+\s+(connected|disconnected)\s+'
                                  r'[- 0-9a-zA-Z]+\s+\d+x\d+\s+\d+\s+\d+')
    connected = 0
    for line in modetest_output.splitlines():
        connector_match = re.match(modetest_connector_pattern, line)
        if connector_match is not None:
            if connector_match.group(1) == 'connected':
                connected = connected + 1

    return connected;

def _get_num_outputs_x():
    """
    Parses the output of xrandr to determine the number of connected displays
    @return: The number of connected displays
    """
    xrandr_state = get_xrandr_output_state()
    output_states = [xrandr_state[name] for name in xrandr_state]
    return sum([1 if is_enabled else 0 for is_enabled in output_states])

def get_num_outputs_on():
    """
    Retrieves the number of connected outputs that are on.

    Return value: integer value of number of connected outputs that are on.
    """

    if utils.is_freon():
        return _get_num_outputs_freon()
    else:
        return _get_num_outputs_x()

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
            output.startswith('DVI') or
            output.startswith('VGA')):
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
