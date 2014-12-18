# Copyright 2014 The Chromium OS Authors. All rights reserved.
# Use of this source code is governed by a BSD-style license that can be
# found in the LICENSE file.

from autotest_lib.client.common_lib import error
from autotest_lib.client.common_lib.cros.tendo import privetd_helper
from autotest_lib.server import test

class privetd_PrivetInfo(test.test):
    """This test verifies that the privetd responds to /privet/info request and
    returns the expected JSON response object.
    """
    version = 1

    def warmup(self, host):
        self.helper = privetd_helper.PrivetdHelper(host=host)
        self.helper.restart_privetd(log_verbosity=3, enable_ping=True)
        self.helper.ping_server()  # Make sure the server is up and running.


    def cleanup(self, host):
        self.helper.restart_privetd()


    def validate_api(self, apis):
        """Validates the 'api' section of /privet/info response.

        @param apis: an array of API urls from JSON.

        """
        expected = ['/privet/info',
                    '/privet/v3/auth',
                    '/privet/v3/pairing/confirm',
                    '/privet/v3/pairing/start',
                    '/privet/v3/setup/start',
                    '/privet/v3/setup/status']
        for api in expected:
            if api not in apis:
                raise error.TestFail('Expected API URL %s is not found' % api)


    def validate_authentication(self, auth):
        """Validates the 'authentication' section of /privet/info response.

        @param auth: the authentication dict from JSON.

        """
        expected = {'crypto': ['p224_spake2'],
                    'mode': ['anonymous', 'pairing'],
                    'pairing': ['embeddedCode']};
        if auth != expected:
            raise error.TestFail('Expected authentication: %r, given: %r'
                                 % (auth, expected))


    def run_once(self, host):
        json_data = self.helper.send_privet_request(privetd_helper.URL_INFO)

        # Do some sanity checks on the returned JSON object.
        if json_data['version'] != '3.0':
            raise error.TestFail('Expected privet version 3.0')
        self.validate_api(json_data['api'])
        self.validate_authentication(json_data['authentication'])
