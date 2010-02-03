#!/usr/bin/python
#
# Copyright (c) 2010 The Chromium Authors. All rights reserved.
# Use of this source code is governed by a BSD-style license that can be
# found in the LICENSE file.

__author__ = 'kdlucas@chromium.org (Kelly Lucas)'

import os

from autotest_lib.client.bin import test, utils
from autotest_lib.client.common_lib import error


class video_Resolution(test.test):
    """
    Verify the current screen resolution is supported.
    """
    version = 1

    def get_resolution(self):
        """
        Get the current video resolution.
        Returns:
            string: represents the video resolution.
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

        linesout = output.split('\n')
        for line in linesout:
            if 'Screen 0' in line:
                sections = line.split(',')
                for item in sections:
                    if 'current' in item:
                        res = item.split()
                        return '%s%s%s' % (res[1], res[2], res[3])

        return None


    def run_once(self):

        supported_resolutions = ['1280x800', '1366x768']
        res = self.get_resolution()

        if res not in supported_resolutions:
            raise error.TestFail('%s is not a supported resoltuion' % res)
