# Copyright (c) 2011 The Chromium OS Authors. All rights reserved.
# Use of this source code is governed by a BSD-style license that can be
# found in the LICENSE file.

import dbus
import gobject
import logging
import sys
import os
import tempfile

from autotest_lib.client.bin import test, utils
from autotest_lib.client.common_lib import autotemp, error
from autotest_lib.client.cros import constants, cros_ui, cryptohome, login
from autotest_lib.client.cros import cros_ownership_test, ownership

from dbus.mainloop.glib import DBusGMainLoop


class login_OwnershipRetaken(cros_ownership_test.OwnershipTest):
    version = 1

    _tempdir = None
    _got_new_key = False
    _got_new_policy = False

    def setup(self):
        os.chdir(self.srcdir)
        utils.make('OUT_DIR=.')


    def __handle_new_key(self, success):
        self._got_new_key = (success == 'success')


    def __handle_new_policy(self, success):
        self._got_new_policy = (success == 'success')


    def __received_signals(self):
        """Process dbus events"""
        context = gobject.MainLoop().get_context()
        while context.iteration(False):
            pass
        return self._got_new_key and self._got_new_policy


    def __reset_signal_state(self):
        self._got_new_policy = self._got_new_key = False


    def initialize(self):
        super(login_OwnershipRetaken, self).initialize()
        # Start with a clean slate wrt ownership
        cros_ui.stop()
        cryptohome.remove_vault(self._testuser)
        cryptohome.mount_vault(self._testuser, self._testpass, create=True)
        ownership.clear_ownership()
        cros_ui.start()
        login.wait_for_browser()
        DBusGMainLoop(set_as_default=True)
        ownership.listen_to_session_manager_signal(self.__handle_new_key,
                                                   'SetOwnerKeyComplete')
        ownership.listen_to_session_manager_signal(self.__handle_new_policy,
                                                   'PropertyChangeComplete')


    def run_once(self):
        pkey = ownership.known_privkey()
        pubkey = ownership.known_pubkey()
        sm = ownership.connect_to_session_manager()

        # Pre-configure some owner settings, including initial key.
        poldata = self.build_policy_data(owner=self._testuser,
                                         guests=False,
                                         new_users=True,
                                         roaming=True,
                                         whitelist=(self._testuser, 'a@b.c'),
                                         proxies={ 'proxy_mode': 'direct' })
        policy_string = self.generate_policy(pkey, pubkey, poldata)
        self.push_policy(policy_string, sm)


        # wait for new-owner-key signal, property-changed signal.
        login.wait_for_ownership()

        # grab key, ensure that it's the same as the known key.
        if (utils.read_file(constants.OWNER_KEY_FILE) != pubkey):
            raise error.TestFail('Owner key should have changed!')

        # Start a new session, which will trigger the re-taking of ownership.
        if not sm.StartSession(self._testuser, ''):
            raise error.TestFail('Could not start session for owner')

        # wait for new-owner-key signal, property-changed signal.
        utils.poll_for_condition(condition=lambda: self.__received_signals(),
                                 desc='Retaking of ownership complete.',
                                 timeout=constants.DEFAULT_OWNERSHIP_TIMEOUT)

        # grab key, ensure that it's different than known key
        if (utils.read_file(constants.OWNER_KEY_FILE) == pubkey):
            raise error.TestFail('Owner key should have changed!')

        # RetrievePolicy, check sig against new key, check properties
        retrieved_policy = sm.RetrievePolicy(byte_arrays=True)
        if retrieved_policy is None:
            raise error.TestFail('Policy not found')
        self.compare_policy_response(retrieved_policy,
                                     owner=self._testuser,
                                     guests=False,
                                     new_users=True,
                                     roaming=True,
                                     whitelist=(self._testuser, 'a@b.c'),
                                     proxies={ 'proxy_mode': 'direct' })



    def cleanup(self):
        cryptohome.unmount_vault()
        if self._tempdir: self._tempdir.clean()
        cros_ui.start(allow_fail=True)
        super(login_OwnershipRetaken, self).cleanup()
