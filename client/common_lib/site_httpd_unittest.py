#!/usr/bin/python

# Copyright (c) 2010 The Chromium OS Authors. All rights reserved.
# Use of this source code is governed by a BSD-style license that can be
# found in the LICENSE file.

"""HTTPlistener unittest."""

import logging, sys, threading, urllib
from site_httpd import HTTPListener


def test():
    test_server = HTTPListener(8000, docroot='/tmp')
    post_done = test_server.add_wait_url("/post_test",
                                         matchParams={'test': 'passed'})
    def _Spam():
        while not post_done.is_set():
            print 'TEST: server running'
            post_done.wait()
        return
    test_server.run()
    t = threading.Thread(target=_Spam).start()
    params = urllib.urlencode({'test': 'passed'})
    err = 1
    post_resp = ''
    try:
        post_resp = urllib.urlopen('http://localhost:8000/post_test',
                                   params).read()
    except IOError, e:
        pass
    if not (post_done.is_set() and
            test_server.get_form_entries()['test'] != 'passed'):
        print 'FAILED'
    else:
        print 'PASSED'
        err = 0
    get_done = test_server.add_wait_url("/get_test")
    get_resp = ''
    try:
      # A simple 404 is enough proof for GET.
      get_resp = urllib.urlopen('http://localhost:8000/get_test').read()
    except IOError, e:
      pass
    if not (get_done.is_set() and get_resp):
      print 'FAILED'
    else:
      print 'PASSED'
      err = 0
    test_server.stop()
    return err


def run_server():
    """Example method showing how to start a HTTPListener."""
    test_server = HTTPListener(8000, docroot='/tmp')
    latch = test_server.add_wait_url('/quitquitquit')
    test_server.run()
    logging.info('server started')
    while not latch.is_set():
        try:
            latch.wait(1)
        except KeyboardInterrupt:
            sys.exit()
    test_server.stop()
    return


if __name__ == '__main__':
    if len(sys.argv) > 1:
        run_server()
    else:
        test()
