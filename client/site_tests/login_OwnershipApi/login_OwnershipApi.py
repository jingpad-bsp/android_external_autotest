# Copyright (c) 2011 The Chromium OS Authors. All rights reserved.
# Use of this source code is governed by a BSD-style license that can be
# found in the LICENSE file.

import dbus
import dbus.glib
import gobject
import logging
import os
import sys
import tempfile

from autotest_lib.client.bin import test, utils
from autotest_lib.client.common_lib import autotemp, error
from autotest_lib.client.cros import constants, cros_ui, cryptohome, login
from autotest_lib.client.cros import ownership


class login_OwnershipApi(test.test):
    version = 1

    _testuser = 'cryptohometest@chromium.org'
    _testpass = 'testme'
    _poldata = 'hooberbloob'

    _tempdir = None

    def setup(self):
        os.chdir(self.srcdir)
        utils.make('OUT_DIR=.')


    def __unlink(self, filename):
        try:
            os.unlink(filename)
        except (IOError, OSError) as error:
            logging.info(error)

    def initialize(self):
        self.__unlink(constants.OWNER_KEY_FILE)
        self.__unlink(constants.SIGNED_PREFERENCES_FILE)
        self.__unlink(constants.SIGNED_POLICY_FILE)
        login.refresh_login_screen()
        cryptohome.remove_vault(self._testuser)
        cryptohome.mount_vault(self._testuser, self._testpass, create=True)
        self._tempdir = autotemp.tempdir(unique_id=self.__class__.__name__)
        # to prime nssdb.
        tmpname = self.__generate_temp_filename()
        cros_ui.xsystem_as('HOME=%s %s %s' % (constants.CRYPTOHOME_MOUNT_PT,
                                              constants.KEYGEN,
                                              tmpname))
        os.unlink(tmpname)
        super(login_OwnershipApi, self).initialize()


    def __generate_temp_filename(self):
        just_for_name = tempfile.NamedTemporaryFile(mode='w', delete=True)
        basename = just_for_name.name
        just_for_name.close()  # deletes file.
        return basename


    def __log_and_stop(self, ret_code):
        logging.info("exited %s" % ret_code)
        self._loop.quit()


    def __log_err_and_stop(self, e):
        logging.debug(e)
        self._loop.quit()


    def run_once(self):
        keyfile = ownership.generate_and_register_owner_keypair(self._testuser,
                                                                self._testpass)
        # Pull in protobuf definitions.
        sys.path.append(self.srcdir)
        from device_management_backend_pb2 import PolicyFetchResponse

        # open DBus connection to session_manager
        bus = dbus.SystemBus()
        proxy = bus.get_object('org.chromium.SessionManager',
                               '/org/chromium/SessionManager')
        sm = dbus.Interface(proxy, 'org.chromium.SessionManagerInterface')

        policy_proto = PolicyFetchResponse()
        policy_proto.policy_data = self._poldata
        policy_proto.policy_data_signature = ownership.sign(keyfile,
                                                            self._poldata)
        sm.StorePolicy(dbus.ByteArray(policy_proto.SerializeToString()),
                       byte_arrays=True,
                       reply_handler=self.__log_and_stop,
                       error_handler=self.__log_err_and_stop)

        self._loop = gobject.MainLoop()
        self._loop.run()

        retrieved_policy = sm.RetrievePolicy(byte_arrays=True)
        if retrieved_policy != policy_proto.SerializeToString():
            raise error.TestFail('Policy should not be %s' % retrieved_policy)


    def cleanup(self):
        cryptohome.unmount_vault()
        self._tempdir.clean()
        super(login_OwnershipApi, self).cleanup()
