# Copyright (c) 2011 The Chromium OS Authors. All rights reserved.
# Use of this source code is governed by a BSD-style license that can be
# found in the LICENSE file.

import logging
import os
import re
import urllib

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
    """Replay raw touch gestures and check how the browser interprets them.

    This test runs a series of HTML/JS test pages (somewhat similar to WebKit
    layout tests). Each HTML page asks to replay a recording of touch screen
    gesture(s) and then reports whether the observed results were as expected.

    """
    version = 1

    def initialize(self, creds='$default', testfile="example.html", **dargs):
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

        self.testfile = testfile
        self.timeout = 120 #[sec] time to wait for each subtest to complete
        self.port = 8000
        tests_dir = 'tests'
        self.tests_dir = os.path.join(self.bindir, tests_dir)
        self.test_url = 'http://localhost:%s/%s/' % (self.port, tests_dir)
        self.gestures_dir = os.path.join(self.bindir, 'gestures')

        self.reported_status = None
        self._testServer = httpd.HTTPListener(self.port, docroot=self.bindir)
        self._testServer.add_url_handler('/replay', self.replay_url_handler)
        self._testServer.add_url_handler('/msg', self.msg_url_handler)
        self._testServer.add_url_handler('/done', self.done_url_handler)
        # Fire up the web server thread.
        self._testServer.run()
        super(desktopui_TouchScreen, self).initialize(creds, **dargs)

    def replay_gesture(self, gesture_file):
        logging.info('Replaying gesture file: %s' % gesture_file)
        utils.system(
            '/usr/local/bin/evemu-play %s < %s/%s' %
                (self.touch_dev, self.gestures_dir, gesture_file))

    def replay_url_handler(self, fh, form):
        gestures = urllib.unquote(form['gesture'].value).split()
        for gesture in gestures:
            self.replay_gesture(gesture + '.dat')
        fh.write_post_response(form)

    def msg_url_handler(self, fh, form):
        msg = urllib.unquote(form['msg'].value)
        logging.info(msg)
        fh.write_post_response(form)

    def done_url_handler(self, fh, form):
        self.reported_status = form['status'].value
        fh.write_post_response(form)

    def run_subtest(self, test_name):
        self.reported_status = None
        self.pyauto.NavigateToURL(self.test_url + test_name)
        latch = self._testServer.add_wait_url('/done')
        latch.wait(self.timeout)
        msg = "'%s' reported by %s" % (self.reported_status, test_name)
        if not latch.is_set():
            logging.error('Timed out waiting for %s test to report status.' %
                            test_name)
        elif self.reported_status != 'PASS':
            logging.error(msg)
        else:
            logging.info(msg)
        return self.reported_status

    def run_once(self):
        logging.info('Running HTML test %s' % self.testfile)
        result = self.run_subtest(self.testfile)
        if result != 'PASS':
            raise error.TestFail('HTML test %s did not pass.'
                                    % self.testfile)
