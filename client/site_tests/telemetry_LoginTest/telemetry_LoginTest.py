# Copyright (c) 2013 The Chromium OS Authors. All rights reserved.
# Use of this source code is governed by a BSD-style license that can be
# found in the LICENSE file.

import os

from autotest_lib.client.bin import test
from autotest_lib.client.common_lib import error
from autotest_lib.client.common_lib.cros import chrome

class telemetry_LoginTest(test.test):
    """This is a client side Telemetry Login Test."""
    version = 1


    def run_once(self):
        """
        This test imports telemetry, restarts and connects to chrome, navigates
        the login flow and checks to ensure that the login process is
        completed.
        """
        extension_path = os.path.join(os.path.dirname(__file__),
                                      'login_status_ext')
        with chrome.Chrome(logged_in=True,
                           extension_paths=[extension_path]) as cr:
            # By creating a browser and using 'with' any code in this section
            # is wrapped by a login/logout.
            if not os.path.exists('/var/run/state/logged-in'):
                raise error.TestFail('Failed to log into the system.')

            extension = cr.get_extension(extension_path)
            if not extension:
                raise error.TestFail('Failed to find loaded extension %s'
                                     % extension_path)

            # Ensure private api loginStatus can be called.
            extension.ExecuteJavaScript('''
                chrome.autotestPrivate.loginStatus(function(s) {
                  window.__login_status = s;
                });
            ''')
            login_status = extension.EvaluateJavaScript(
                    'window.__login_status')
            if type(login_status) != dict:
                raise error.TestFail('LoginStatus type mismatch %r'
                                     % type(login_status))

            if not login_status['isRegularUser']:
                raise error.TestFail('isRegularUser should be True')
            if login_status['isGuest']:
                raise error.TestFail('isGuest should be False')
            if login_status['email'] != chrome.LOGIN_USER:
                raise error.TestFail('user email mismatch %s'
                                     % login_status['email'])

