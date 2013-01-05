# Copyright (c) 2013 The Chromium OS Authors. All rights reserved.
# Use of this source code is governed by a BSD-style license that can be
# found in the LICENSE file.

import logging, os, pwd, stat

from autotest_lib.client.common_lib import error
from autotest_lib.client.cros import auth_server, cros_ui_test, dns_server

class enterprise_Policies(cros_ui_test.UITest):
    version = 1


    def __authenticator(self, email, password):
        """Respond positively to any auth attempt."""
        return True


    def _file_exists(self, path):
        """Verify existence of file at 'path'."""
        if path is None:
            raise error.TestError('Warning: invalid path (%s).' % path)
        if not os.path.exists(path):
            raise error.TestFail('Failure: file %s does not exist.' % path)
        return True


    def _owner_mode_matches(self, path, expected_owner, expected_mode):
        """Checks if the file at 'path' is owned by 'expected_owner', and has
        permissions mode matching 'expected_mode'. Returns True if they match,
        else returns False. Logs any mismatches to logging.error.
        """
        s = os.stat(path)
        actual_owner = pwd.getpwuid(s.st_uid).pw_name
        actual_mode = stat.S_IMODE(s.st_mode)
        if (expected_owner != actual_owner or
            expected_mode != actual_mode):
            raise error.TestFail("%s - Expected %s:%s, saw %s:%s" %
                          (path, expected_owner, oct(expected_mode),
                           actual_owner, oct(actual_mode)))
        return True


    def initialize(self, creds='$default'):
        """Override superclass to provide a default value for the creds param.

        This is important for our class, since non-user sessions (AKA "browse
        without signing in") don't exercise the code we want to test.

        @param creds: Per cros_ui_test.UITest. Herein, default is '$default'.
        """
        assert creds, "Must use user credentials for this test."
        super(enterprise_Policies, self).initialize(creds,
                                                    is_creating_owner=True)


    def start_authserver(self):
        """Override superclass to use our authenticator."""
        super(enterprise_Policies, self).start_authserver(
            authenticator=self.__authenticator)


    def run_once(self):
        """Verify properties of install_attributes.pb, policy, key files."""
        install_attributes = "/home/.shadow/install_attributes.pb"
        self._file_exists(install_attributes)

        # TODO(scunningham) Correct mode should be 0644. Initialize() sets
        # it to 0600. Change expected mode to 0644 after crosbug.com/37633
        # is fixed.
        self._owner_mode_matches(install_attributes, "root", 0600)

        whitelist_policy = "/var/lib/whitelist/policy"
        self._file_exists(whitelist_policy)
        self._owner_mode_matches(whitelist_policy, "root", 0604)

        whitelist_key = "/var/lib/whitelist/owner.key"
        self._file_exists(whitelist_key)
        self._owner_mode_matches(whitelist_key, "root", 0604)


    def cleanup(self):
        super(enterprise_Policies, self).cleanup()
        self.write_perf_keyval(self.get_auth_endpoint_misses())
