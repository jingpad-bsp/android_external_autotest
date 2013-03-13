# Copyright (c) 2013 The Chromium OS Authors. All rights reserved.
# Use of this source code is governed by a BSD-style license that can be
# found in the LICENSE file.

import grp
import logging
import os
import pwd
import stat

from autotest_lib.client.common_lib import error
from autotest_lib.client.common_lib import utils
from autotest_lib.client.cros import cros_ui_test
from autotest_lib.client.cros import login

_FILE_PATH_NAME = '/home/.shadow/install_attributes.pb'
_FILE_ATTRIBUTES = {'owner':'root','group':'root','mode':0644}


class enterprise_InstallAttributes(cros_ui_test.UITest):
    """
    This test verifies that taking device ownership creates the
    install_attributes.pb file with the correct external attributes
    and internal enterprise properties.
    """
    version = 1


    def __authenticator(self, email, password):
        """Respond positively to any auth attempt."""
        return True


    def _verify_file_attributes(self):
        """Verify the external attributes of the file.

        Checks that the install_attributes.pb file exists and has the correct
        attributes: owner, group, and mode.

        """
        # Verify that the file exists.
        if not os.path.exists(_FILE_PATH_NAME):
            raise error.TestFail('file %s does not exist.' %
                                 _FILE_PATH_NAME)

        # Verify that the file's attributes are correct.
        if not self._attributes_match(_FILE_PATH_NAME, _FILE_ATTRIBUTES):
            raise error.TestFail('file %s has incorrect attributes.' %
                                 _FILE_PATH_NAME)


    def _attributes_match(self, fname, attributes):
        """Check that the file has the expected external attributes.

        Checks that the file at 'fname' has the expected external attributes:
        owner, group, and mode. Returns True if all attributes match
        expectations; otherwise returns False.

        @param fname: path and name of file to check
        @param attributes: dictionary of owner, group, and mode values

        """
        s = os.stat(fname)
        owner = pwd.getpwuid(s.st_uid).pw_name
        group = grp.getgrgid(s.st_gid).gr_name
        mode = stat.S_IMODE(s.st_mode)
        if (owner == attributes['owner'] and
            group == attributes['group'] and
            mode == attributes['mode']):
            return True
        else:
            logging.error('File %s: Expected %s:%s %s; Saw %s:%s %s',
                          fname, attributes['owner'], attributes['group'],
                          oct(attributes['mode']), owner, group, oct(mode))
            return False


    def initialize(self, creds='$default'):
        """Override superclass to provide a default value for the creds param.

        User creds are important for this class, since non-user sessions (AKA
        "browse without signing in") do not exercise the code under test.

        @param creds: Per cros_ui_test.UITest. Herein, default is '$default'.

        """
        assert creds, 'Must use user credentials for this test.'
        self.auto_login = False # Login is perfomed in run_once.
        super(enterprise_InstallAttributes, self).initialize(creds,
                                                     is_creating_owner=True)


    def start_authserver(self):
        """Override superclass to use our authenticator."""
        super(enterprise_InstallAttributes, self).start_authserver(
            authenticator=self.__authenticator)


    def run_once(self):
        """Verify attributes and properties of Install Attributes file."""
        self.login(self.username, self.password)
        login.wait_for_ownership()

        # Verify the external attributes of the file.
        self._verify_file_attributes()

        # Verify the internal properties of the file.
        cmd = ('cryptohome --action=install_attributes_get '
               '--name=enterprise.owned')
        cmd_output = utils.system_output(cmd, ignore_status=True)
        if cmd_output != 'true':
            raise error.TestFail('enterprise.owned is not true')

        cmd = ('cryptohome --action=install_attributes_get '
               '--name=enterprise.mode')
        cmd_output = utils.system_output(cmd, ignore_status=True)
        if cmd_output != 'enterprise':
            raise error.TestFail('enterprise.mode is not enterprise')


    def cleanup(self):
        super(enterprise_InstallAttributes, self).cleanup()
