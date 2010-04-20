#!/usr/bin/python

# Copyright (c) 2010 The Chromium OS Authors. All rights reserved.
# Use of this source code is governed by a BSD-style license that can be
# found in the LICENSE file.

"""GoogleAuthServer unittest."""

import logging, os, sys, threading, time, unittest, urllib
from autotest_lib.client.bin import chromeos_constants
from autotest_lib.client.common_lib import site_auth_server
from site_auth_server import GoogleAuthServer

class test_auth_server(unittest.TestCase):
    def setUp(self):
        print "starting"
        self._ssl_port=50030
        creds_path = (os.path.dirname(os.path.realpath( __file__)) +
                      '/site_httpd_unittest_server')

        self._test_server = GoogleAuthServer(port=self._ssl_port,
                                             cert_path=(creds_path+'.pem'),
                                             key_path=(creds_path+'.key'))
        self._test_server.run()


    def tearDown(self):
        print "tearing down"
        self._test_server.stop()


    def test_client_login(self):
        args = urllib.urlencode({'Email': 'me@example.com', 'Passwd': 'fake'})
        try:
            cl_resp = urllib.urlopen(
                'https://localhost:%s%s' %
                (self._ssl_port, chromeos_constants.CLIENT_LOGIN_URL),
                args).read()
        except IOError, e:
            pass
        self._test_server.wait_for_client_login()
        return cl_resp


    def test_issue_token(self):
        args = self.test_client_login().replace('\n','&')
        try:
            it_resp = urllib.urlopen('https://localhost:%s%s' %
                                     (self._ssl_port,
                                      chromeos_constants.ISSUE_AUTH_TOKEN_URL),
                                     args).read()
        except IOError, e:
            pass
        self._test_server.wait_for_issue_token()
        return it_resp


    def test_token_auth(self):
        args = self.test_issue_token()
        try:
            ta_format = ('https://localhost:%s%s?auth=%s&' +
                         'continue=https://localhost:%s/webhp')
            ta_resp = urllib.urlopen(
                ta_format % (self._ssl_port,
                             chromeos_constants.TOKEN_AUTH_URL,
                             args,
                             self._ssl_port)).read()
        except IOError, e:
            pass
        self._test_server.wait_for_test_over()
