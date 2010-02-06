# Copyright (c) 2010 The Chromium OS Authors. All rights reserved.
# Use of this source code is governed by a BSD-style license that can be
# found in the LICENSE file.

import logging, os, utils
from autotest_lib.client.bin import test
from autotest_lib.client.common_lib import error

class browser_UrlFetch(test.test):
    version = 1

    def run_once(self):
        url = 'http://www.youtube.com'
        cookie_expected = 'VISITOR_INFO1_LIVE'

        os.chdir(self.bindir)

        try:
          # Stop chrome from restarting and kill login manager
          utils.system('touch /tmp/disable_chrome_restart')
          utils.system('killall chrome')

          # Copy over chrome, chrome.pak, etc needed for test
          utils.system('cp -r %s/* .' % '/opt/google/chrome')

          # Setup environment
          make_env = 'source ./required_environment.sh'
          utils.system('%s && ./url_fetch_test --url=%s --wait_cookie_name=%s'
                       % (make_env, url, cookie_expected))

          #TODO(sosa@chromium.org) - Find a way to clean up besides rebooting
          utils.system('shutdown -r 1 &')
        except error.CmdError, e:
            logging.debug(e)
            raise error.TestFail('Url Fetch test was unsuccessful for %s %s %s'
                                 % (url, cookie_expected, os.getcwd()))
