# Copyright (c) 2011 The Chromium OS Authors. All rights reserved.
# Use of this source code is governed by a BSD-style license that can be
# found in the LICENSE file.

"""
Helper server used for local debuggin of the HTML page on development machine.
This file does not run as part of the actual test on target device.
"""

import os
import sys
import time

# paths are considered to be relative to
# src/third_party/autotest/files/client/site_tests/desktopui_TouchScreen

# httpd module lives here
sys.path.append(os.path.abspath('../../cros'))
import httpd


def url_handler(fh, form):
    for key in form.keys():
        print key, ':', form[key].value

def exit_url_handler(fh, form):
    global listener
    listener.stop()
    sys.exit()

def replay_url_handler(fh, form):
    print 'Replay ', form['gesture'].value
    time.sleep(2) # real gesture would take some time
    fh.write_post_response(form)

def done_url_handler(fh, form):
    print 'Done ', form['status'].value
    fh.write_post_response(form)

def msg_url_handler(fh, form):
    print 'Message: ', form['msg'].value
    fh.write_post_response(form)

listener = httpd.HTTPListener(8000, docroot=os.path.abspath('.'))
listener.add_url_handler('/interaction/test', url_handler)
listener.add_url_handler('/exit', exit_url_handler)
listener.add_url_handler('/replay', replay_url_handler)
listener.add_url_handler('/done', done_url_handler)
listener.add_url_handler('/msg', msg_url_handler)
listener.run()
