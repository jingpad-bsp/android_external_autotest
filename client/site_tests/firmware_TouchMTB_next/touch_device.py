# Copyright (c) 2012 The Chromium OS Authors. All rights reserved.
# Use of this source code is governed by a BSD-style license that can be
# found in the LICENSE file.

"""Touch device module provides some touch device related attributes."""

import glob
import os
import re

import common_util


class TouchDevice:
    """A class about touch device properties."""
    def __init__(self, device_node=None, is_touchscreen=False):
        self.device_info_file = '/proc/bus/input/devices'
        self.device_node = (device_node if device_node
                                else self.get_device_node(is_touchscreen))

    def get_device_node(self, is_touchscreen):
        """Get the touch device node through xinput
           Touchscreens have a different device name, so this
           chooses between them.  Otherwise they are the same.

           The resulting string looks like /dev/input/event8
        """
        cmd = '/opt/google/'
        if is_touchscreen:
            cmd = os.path.join(cmd, 'touchscreen/tscontrol')
        else:
            cmd = os.path.join(cmd, 'touchpad/tpcontrol')
        cmd += ' status | grep "Device Node"'
        device_node_str = common_util.simple_system_output(cmd)
        device_node = device_node_str.split(':')[-1].strip().strip('"')
        return device_node

    def get_dimensions_in_mm(self):
        """Get the width and height in mm of the device."""
        (left, right, top, bottom,
                resolution_x, resolution_y) = self.get_resolutions()
        width = float((right - left)) / resolution_x
        height = float((bottom - top)) / resolution_y
        return (width, height)

    def get_resolutions(self, device_description=None):
        """Get the resolutions in x and y axis of the device."""
        _, _, _, _, resolution_x, resolution_y = self.get_abs_axes(
                device_description)
        return (resolution_x, resolution_y)

    def get_edges(self, device_description=None):
        """Get the left, right, top, and bottom edges of the device."""
        left, right, top, bottom, _, _ = self.get_abs_axes(
                device_description)
        return (left, right, top, bottom)

    def get_abs_axes(self, device_description=None):
        """Get information about min, max, and resolution from ABS_X and ABS_Y

        Example of ABS_X:
                A: 00 0 1280 0 0 12
        Example of ABS_y:
                A: 01 0 1280 0 0 12
        """
        pattern = 'A:\s*%s\s+(\d+)\s+(\d+)\s+(\d+)\s+(\d+)\s+(\d+)'
        pattern_x = pattern % '00'
        pattern_y = pattern % '01'
        cmd = 'evemu-describe %s' % self.device_node
        if device_description is None:
            device_description = common_util.simple_system_output(cmd)
        found_x = found_y = False
        left = right = top = bottom = None
        resolution_x = resolution_y = None
        if device_description:
            for line in device_description.splitlines():
                if not found_x:
                    result = re.search(pattern_x, line, re.I)
                    if result:
                        left = int(result.group(1))
                        right = int(result.group(2))
                        resolution_x = int(result.group(5))
                        found_x = True
                if not found_y:
                    result = re.search(pattern_y, line, re.I)
                    if result:
                        top = int(result.group(1))
                        bottom = int(result.group(2))
                        resolution_y = int(result.group(5))
                        found_y = True
        return (left, right, top, bottom, resolution_x, resolution_y)

    def get_dimensions(self, device_description=None):
        """Get the vendor-specified dimensions of the touch device."""
        left, right, top, bottom = self.get_edges(device_description)
        return (right - left, bottom - top)

    def get_display_geometry(self, screen_size, display_ratio):
        """Get a preferred display geometry when running the test."""
        display_ratio = 0.8
        dev_width, dev_height = self.get_dimensions()
        screen_width, screen_height = screen_size

        if 1.0 * screen_width / screen_height <= 1.0 * dev_width / dev_height:
            disp_width = int(screen_width * display_ratio)
            disp_height = int(disp_width * dev_height / dev_width)
            disp_offset_x = 0
            disp_offset_y = screen_height - disp_height
        else:
            disp_height = int(screen_height * display_ratio)
            disp_width = int(disp_height * dev_width / dev_height)
            disp_offset_x = 0
            disp_offset_y = screen_height - disp_height

        return (disp_width, disp_height, disp_offset_x, disp_offset_y)

    def _touch_input_name_re_str(self):
        pattern_str = ('touchpad', 'trackpad')
        return '(?:%s)' % '|'.join(pattern_str)

    def get_touch_input_dir(self):
        """Get touch device input directory."""
        input_root_dir = '/sys/class/input'
        input_dirs = glob.glob(os.path.join(input_root_dir, 'input*'))
        re_pattern = re.compile(self._touch_input_name_re_str(), re.I)
        for input_dir in input_dirs:
            filename = os.path.join(input_dir, 'name')
            if os.path.isfile(filename):
                with open(filename) as f:
                    for line in f:
                        if re_pattern.search(line) is not None:
                            return input_dir
        return None

    def get_firmware_version(self):
        """Probe the firmware version."""
        input_dir = self.get_touch_input_dir()
        device_dir = 'device'

        # Get the re search pattern for firmware_version file name
        fw_list = ('firmware', 'fw')
        ver_list = ('version', 'id')
        sep_list = ('_', '-')
        re_str = '%s%s%s' % ('(?:%s)' % '|'.join(fw_list),
                             '(?:%s)' % '|'.join(sep_list),
                             '(?:%s)' % '|'.join(ver_list))
        re_pattern = re.compile(re_str, re.I)

        if input_dir is not None:
            device_dir = os.path.join(input_dir, 'device', '*')
            for f in glob.glob(device_dir):
                if os.path.isfile(f) and re_pattern.search(f):
                    with open (f) as f:
                        for line in f:
                            return line.strip('\n')
        return 'unknown'
