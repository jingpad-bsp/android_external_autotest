#!/usr/bin/python
#
# Copyright (c) 2010 The Chromium Authors. All rights reserved.
# Use of this source code is governed by a BSD-style license that can be
# found in the LICENSE file.

__author__ = 'kdlucas@chromium.org (Kelly Lucas)'

import os, re

from autotest_lib.client.bin import test, utils
from autotest_lib.client.common_lib import error


class hardware_Resolution(test.test):
    """
    Verify the current screen resolution is supported.
    """
    version = 1

    def get_xrandr_output(self):
        """
        Retrieves the output of xrandr as a list of strings.
        """
        cmd = 'xrandr'
        # TODO:remove oldxauth when slim is deprecated.
        oldxauth = '/var/run/slim.auth'
        newxauth = '/home/chronos/.Xauthority'
        # The new login manager uses XAUTHORITY=/home/chronos/.Xauthority
        # so we need to check which file to use.
        if os.path.isfile(oldxauth):
            xauth = oldxauth
        else:
            xauth = newxauth

        environment = 'DISPLAY=:0.0 XAUTHORITY=%s' % xauth
        output = utils.system_output('%s %s' % (environment, cmd))

        return output.split('\n')


    def is_lvds_res(self, res, xrandr_output):
        """
        Returns True if the supplied resolution is associated with
        an LVDS connection.
        """
        search_str = r'LVDS\d+ connected ' + res
        for line in xrandr_output:
            if re.match(search_str, line):
                return True;

        return False


    def get_current_res(self, xrandr_output):
        """
        Get the current video resolution.
        Returns:
            string: represents the video resolution.
        """
        for line in xrandr_output:
            if 'Screen 0' in line:
                sections = line.split(',')
                for item in sections:
                    if 'current' in item:
                        res = item.split()
                        return '%s%s%s' % (res[1], res[2], res[3])

        return None


    def run_once(self):
        xrandr_output = self.get_xrandr_output()

        res = self.get_current_res(xrandr_output)
        if not res or not re.match(r'\d+x\d+$', res):
            raise error.TestFail('%s is not a valid resolution' % res)

        supported_lvds_resolutions = ['1280x800', '1366x768']
        if self.is_lvds_res(res, xrandr_output) and \
           res not in supported_lvds_resolutions:
            raise error.TestFail('%s is not a supported LVDS resolution' % res)
