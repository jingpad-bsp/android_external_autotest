# Copyright (c) 2011 The Chromium OS Authors. All rights reserved.
# Use of this source code is governed by a BSD-style license that can be
# found in the LICENSE file.

import logging
import re
import time

from autotest_lib.client.bin import utils
from autotest_lib.client.common_lib import error
from autotest_lib.client.cros import cros_ui_test, httpd


def mygrep(fname, substring):
    lines = []
    for line in open(fname, 'rt'):
        if substring in line.lower():
            lines.append(line)
    return lines


class desktopui_TouchScreen(cros_ui_test.UITest):
    """A test that replays raw touch screen events and checks how the browser
    interprets them.

    You can inherit from test.test during develpment to avoid waiting for the
    log in/out cycle of UITest.

    """
    version = 1

    def initialize(self, creds='$default'):
        # Check if the device file is grabbed by X.
        grab_lines = mygrep( '/etc/X11/xorg.conf.d/60-touchscreen-mxt.conf',
                             'GrabDevice' )
        if len(grab_lines) > 0 and 'true' in grab_lines[0]:
            logging.warning('Looks like the device file is grabbed by the X')

        # Find out the touch device file name.
        touch_text = ''.join(mygrep('/var/log/Xorg.0.log', 'touch' ))
        m = re.search(r'/dev/input/event\d+', touch_text)
        if not m:
            raise error.TestError(
                'Could not figure out the touch device name /dev/input/event?')
        self.touch_dev = m.group(0)
        msg = 'Found %s to be the touch device based on Xorg log file'
        logging.info(msg % self.touch_dev)

        # Fire up the web server thread.
        self._test_url = 'http://localhost:8000/interaction.html'
        self._testServer = httpd.HTTPListener(8000, docroot=self.bindir)
        self._testServer.run()
        super(desktopui_TouchScreen, self).initialize(creds)

    def run_once(self, timeout=60):
        # Fire up the browser and wait for onload event from JavaScript
        latch_onload = self._testServer.add_wait_url('/interaction/onload')
        self.pyauto.NavigateToURL(self._test_url)
        latch_onload.wait(timeout)

        if not latch_onload.is_set():
            msg = 'Timeout waiting for initial onload event from the page.'
            raise error.TestError(msg)

        # Replay the gesture and wait for any event to be reported by JS
        latch = self._testServer.add_wait_url('/interaction/test')
        # TODO: Use a gesture file storage later
        gesture_file = 'scroll_both.dat'
        utils.system(
            '/usr/local/bin/evemu-play %s < %s/%s' %
                (self.touch_dev, self.bindir, gesture_file))
        latch.wait(timeout)

        if not latch.is_set():
            raise error.TestFail(
                'Timed out waiting for the page to report an event.')

        results = self._testServer.get_form_entries()
        logging.info('The response:' + str(results))
        if not results:
            raise error.TestFail(
                'Empty response from the browser or no response at all.')
