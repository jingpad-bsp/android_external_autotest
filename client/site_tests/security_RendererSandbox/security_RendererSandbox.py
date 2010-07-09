# Copyright (c) 2010 The Chromium OS Authors. All rights reserved.
# Use of this source code is governed by a BSD-style license that can be
# found in the LICENSE file.


import os, subprocess, time
from autotest_lib.client.bin import site_utils, test, utils
from autotest_lib.client.common_lib import error, site_ui


class security_RendererSandbox(test.test):
    version = 1
    render_pid = -1

    def run_once(self, time_to_wait=20):
        # open browser to google.com.
        session = site_ui.ChromeSession('http://www.google.com')

        try:
            # wait till the page is loaded and poll for the renderer pid
            # if renderer pid is found, it is stored in self.render_pid
            site_utils.poll_for_condition(
                self._get_renderer_pid,
                error.TestFail('Timed out waiting to obtain pid of renderer'),
                time_to_wait)

            #check if renderer is sandboxed
            cwd_contents = os.listdir('/proc/%s/cwd' % self.render_pid)
            if len(cwd_contents) > 0:
                raise error.TestFail('Contents present in the CWD directory')
        finally:
            session.close()


    # queries pgrep for the pid of the renderer. since this function is passed
    # as an argument to site_utils.poll_for_condition, the return values are set
    # to true/false depending on whether a pid has been found
    def _get_renderer_pid(self):                             
        pgrep = subprocess.Popen(['pgrep', '-f', '%s' % 'type=renderer'],
                                 stdout=subprocess.PIPE)
        pids = pgrep.communicate()[0].split()
        if pids:
            self.render_pid = pids[0]
            return True
        else:
            return False