# Copyright (c) 2010 The Chromium OS Authors. All rights reserved.
# Use of this source code is governed by a BSD-style license that can be
# found in the LICENSE file.

import logging, shutil
from autotest_lib.client.common_lib import utils


def xcommand(cmd):
    """
    Add the necessary X setup to a shell command that needs to connect to the X
    server.

    @param cmd: the command line string
    @return a modified command line string with necessary X setup
    """
    return 'DISPLAY=:0 XAUTHORITY=/home/chronos/.Xauthority ' + cmd


class ChromeSession(object):
    """
    A class to start and close Chrome sessions.
    """

    def __init__(self, args='', clean_state=True):
        self._clean_state = clean_state
        self.start(args)


    def __del__(self):
        self.close()


    def start(self, args=''):
        if self._clean_state:
            # Delete previous browser state if any
            shutil.rmtree('/home/chronos/.config/chromium', ignore_errors=True)

        # Open a new browser window as a background job
        cmd = '/opt/google/chrome/chrome --no-first-run ' + args
        cmd = xcommand(cmd)
        cmd = 'su chronos -c \'%s\'' % cmd
        self.job = utils.BgJob(cmd)


    def close(self):
        if self.job is not None:
            utils.nuke_subprocess(self.job.sp)
        self.job = None
