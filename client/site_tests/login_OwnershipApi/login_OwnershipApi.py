# Copyright (c) 2011 The Chromium OS Authors. All rights reserved.
# Use of this source code is governed by a BSD-style license that can be
# found in the LICENSE file.

import dbus
import logging
import os
import tempfile

from autotest_lib.client.bin import test, utils
from autotest_lib.client.common_lib import autotemp, error
from autotest_lib.client.cros import constants, cros_ui, cryptohome, login

class scoped_tempfile(object):
    """A wrapper that provides scoped semantics for temporary files.

    Providing a file path causes the scoped_tempfile to take ownership of the
    file at the provided path.  The file at the path will be deleted when this
    object goes out of scope.  If no path is provided, then a temporary file
    object will be created for the lifetime of the scoped_tempfile

    autotemp.tempfile objects don't seem to play nicely with being
    used in system commands, so they can't be used for my purposes.
    """
    def __init__(self, name=None):
        self.name = name
        if not self.name:
            self.fo = tempfile.TemporaryFile()


    def __del__(self):
        if self.name:
            if os.path.exists(self.name):
                os.unlink(self.name)
        else:
            self.fo.close()  # Will destroy the underlying tempfile


class login_OwnershipApi(test.test):
    version = 1

    _testuser = 'cryptohometest@chromium.org'
    _testpass = 'testme'

    _nssdb = constants.CRYPTOHOME_MOUNT_PT + '/.pki/nssdb'

    _pk12util = 'nsspk12util'
    _opensslp12 = 'openssl pkcs12'
    _opensslx509 = 'openssl x509'
    _opensslrsa = 'openssl rsa'
    _opensslreq = 'openssl req'
    _opensslcrypto = 'openssl sha1'

    _tempdir = None


    def initialize(self):
        try:
            os.unlink(constants.OWNER_KEY_FILE)
            os.unlink(constants.SIGNED_PREFERENCES_FILE)
        except (IOError, OSError) as error:
            logging.info(error)
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


    def __system_output_on_fail(self, cmd):
        """Run a |cmd|, capturing output and logging it only on error."""
        output = None
        try:
            output = utils.system_output(cmd)
        except:
            logging.error(output)
            raise


    def __generate_temp_filename(self):
        just_for_name = tempfile.NamedTemporaryFile(mode='w', delete=True)
        basename = just_for_name.name
        just_for_name.close()  # deletes file.
        return basename


    def __pairgen(self):
        """Generate a self-signed cert and associated private key.

        Generates a self-signed X509 certificate and the associated private key.
        The key is 2048 bits.  The generated material is stored in PEM format
        and the paths to the two files are returned.

        The caller is responsible for cleaning up these files.
        """
        keyfile = self._tempdir.name + 'private.key'
        certfile = self._tempdir.name + 'cert.pem'
        cmd = '%s -x509 -subj %s -newkey rsa:2048 -nodes -keyout %s -out %s' % (
            self._opensslreq, "/CN=me", keyfile, certfile)
        self.__system_output_on_fail(cmd)
        return (keyfile, certfile)


    def __push_to_nss(self, keyfile, certfile, nssdb):
        """Takes a pre-generated key pair and pushes them to an NSS DB.

        Given paths to a private key and cert in PEM format, stores the pair
        in the provided nssdb.
        """
        for_push = scoped_tempfile(self._tempdir.name + "for_push.p12")
        cmd = "%s -export -in %s -inkey %s -out %s " % (
            self._opensslp12, certfile, keyfile, for_push.name)
        cmd += "-passin pass: -passout pass:"

        self.__system_output_on_fail(cmd)

        cmd = "%s -d 'sql:%s' -i %s -W ''" % (self._pk12util,
                                              nssdb,
                                              for_push.name)
        self.__system_output_on_fail(cmd)


    def __cert_extract_pubkey_der(self, pem):
        """Given a PEM-formatted cert, extracts the public key in DER format.

        Pass in an X509 certificate in PEM format, and you'll get back the
        DER-formatted public key as a string.
        """
        outfile = scoped_tempfile(self._tempdir.name + "pubkey.der")
        cmd = "%s -in %s -pubkey -noout " % (self._opensslx509, pem)
        cmd += "| %s -outform DER -pubin -out %s" % (self._opensslrsa,
                                                     outfile.name)
        self.__system_output_on_fail(cmd)
        der = utils.read_file(outfile.name)
        return der


    def __generate_owner_creds(self):
        """Generates a keypair, registered with NSS, and returns key and cert.

        Generates a fresh self-signed cert and private key.  Registers them
        with NSS and then passes back paths to files containing the
        PEM-formatted private key and certificate.
        """
        (keyfile, certfile) = self.__pairgen()
        self.__push_to_nss(keyfile, certfile, self._nssdb)
        return (keyfile, certfile)


    def __generate_and_register_owner_keypair(self):
        """
        Generates keypair, registers with NSS, sets owner key, returns pkey.

        Generates a fresh owner keypair.  Registers keys with NSS,
        puts the owner public key in the right place, ensures that the
        session_manager picks it up, ensures the owner's home dir is
        mounted, and then passes back paths to a file containing the
        PEM-formatted private key.
        """
        (keyfile, certfile) = self.__generate_owner_creds()
        utils.open_write_close(constants.OWNER_KEY_FILE,
                               self.__cert_extract_pubkey_der(certfile))
        login.refresh_login_screen()
        cryptohome.mount_vault(self._testuser, self._testpass, create=False)
        return keyfile


    def __sign(self, pem_key_file, data):
        """Signs |data| with key from |pem_key_file|, returns signature.

        Using the PEM-formatted private key in |pem_key_file|, generates an
        RSA-with-SHA1 signature over |data| and returns the signature in
        a string.
        """
        sig = scoped_tempfile()
        err = scoped_tempfile()
        data_file = scoped_tempfile()
        data_file.fo.write(data)
        data_file.fo.seek(0)

        cmd = '%s -sign %s' % (self._opensslcrypto, pem_key_file)
        try:
            utils.run(cmd,
                      stdin=data_file.fo,
                      stdout_tee=sig.fo,
                      stderr_tee=err.fo)
        except:
            err.fo.seek(0)
            logging.error(err.fo.read())
            raise

        sig.fo.seek(0)
        sig_data = sig.fo.read()
        if len(sig_data) == 0:
            raise error.TestFail("Empty signature!")
        return sig_data


    def run_once(self):
        keyfile = self.__generate_and_register_owner_keypair()

        # open DBus connection to session_manager
        bus = dbus.SystemBus()
        proxy = bus.get_object('org.chromium.SessionManager',
                               '/org/chromium/SessionManager')
        sm = dbus.Interface(proxy, 'org.chromium.SessionManagerInterface')

        sig = self.__sign(keyfile, self._testuser)
        sm.Whitelist(self._testuser, dbus.ByteArray(sig))
        sm.CheckWhitelist(self._testuser)
        sm.Unwhitelist(self._testuser, dbus.ByteArray(sig))
        try:
            sm.CheckWhitelist(self._testuser)
            raise error.TestFail("Should not have found user in whitelist!")
        except dbus.DBusException as e:
            logging.debug(e)


    def cleanup(self):
        cryptohome.unmount_vault()
        self._tempdir.clean()
        super(login_OwnershipApi, self).cleanup()
