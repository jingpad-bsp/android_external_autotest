# Copyright (c) 2012 The Chromium OS Authors. All rights reserved.
# Use of this source code is governed by a BSD-style license that can be
# found in the LICENSE file.

import dbus, logging, os, tempfile

import common, constants, cros_ui, cryptohome
from autotest_lib.client.bin import utils
from autotest_lib.client.common_lib import autotemp, error


class OwnershipError(error.TestError):
    """Generic error for ownership-related failures."""
    pass


class scoped_tempfile(object):
    """A wrapper that provides scoped semantics for temporary files.

    Providing a file path causes the scoped_tempfile to take ownership of the
    file at the provided path.  The file at the path will be deleted when this
    object goes out of scope.  If no path is provided, then a temporary file
    object will be created for the lifetime of the scoped_tempfile

    autotemp.tempfile objects don't seem to play nicely with being
    used in system commands, so they can't be used for my purposes.
    """

    tempdir = autotemp.tempdir(unique_id=__module__)

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


def system_output_on_fail(cmd):
    """Run a |cmd|, capturing output and logging it only on error."""
    output = None
    try:
        output = utils.system_output(cmd)
    except:
        logging.error(output)
        raise


def __unlink(filename):
    try:
        os.unlink(filename)
    except (IOError, OSError) as error:
        logging.info(error)


def clear_ownership():
    __unlink(constants.OWNER_KEY_FILE)
    __unlink(constants.SIGNED_POLICY_FILE)


def connect_to_session_manager():
    """Create and return a DBus connection to session_manager.

    Connects to the session manager over the DBus system bus.  Returns
    appropriately configured DBus interface object.
    """
    bus = dbus.SystemBus()
    proxy = bus.get_object('org.chromium.SessionManager',
                           '/org/chromium/SessionManager')
    return dbus.Interface(proxy, 'org.chromium.SessionManagerInterface')


def listen_to_session_manager_signal(callback, signal):
    """Create and return a DBus connection to session_manager.

    Connects to the session manager over the DBus system bus.  Returns
    appropriately configured DBus interface object.
    """
    bus = dbus.SystemBus()
    bus.add_signal_receiver(
        handler_function=callback,
        signal_name=signal,
        dbus_interface='org.chromium.Chromium',
        bus_name=None,
        path='/org/chromium/SessionManager')

POLICY_TYPE = 'google/chromeos/device'


def assert_has_policy_data(response_proto):
    if not response_proto.HasField("policy_data"):
        raise OwnershipError('Malformatted response.')


def assert_has_device_settings(data_proto):
    if (not data_proto.HasField("policy_type") or
        data_proto.policy_type != POLICY_TYPE or
        not data_proto.HasField("policy_value")):
        raise OwnershipError('Malformatted response.')


def assert_username(data_proto, username):
    if data_proto.username != username:
        raise OwnershipError('Incorrect username.')


def assert_guest_setting(settings, guests):
    if not settings.HasField("guest_mode_enabled"):
        raise OwnershipError('No guest mode setting protobuf.')
    if not settings.guest_mode_enabled.HasField("guest_mode_enabled"):
        raise OwnershipError('No guest mode setting.')
    if settings.guest_mode_enabled.guest_mode_enabled != guests:
        raise OwnershipError('Incorrect guest mode setting.')


def assert_show_users(settings, show_users):
    if not settings.HasField("show_user_names"):
        raise OwnershipError('No show users setting protobuf.')
    if not settings.show_user_names.HasField("show_user_names"):
        raise OwnershipError('No show users setting.')
    if settings.show_user_names.show_user_names != show_users:
        raise OwnershipError('Incorrect show users setting.')


def assert_roaming(settings, roaming):
    if not settings.HasField("data_roaming_enabled"):
        raise OwnershipError('No roaming setting protobuf.')
    if not settings.data_roaming_enabled.HasField("data_roaming_enabled"):
        raise OwnershipError('No roaming setting.')
    if settings.data_roaming_enabled.data_roaming_enabled != roaming:
        raise OwnershipError('Incorrect roaming setting.')


def assert_new_users(settings, new_users):
    if not settings.HasField("allow_new_users"):
        raise OwnershipError('No allow new users setting protobuf.')
    if not settings.allow_new_users.HasField("allow_new_users"):
        raise OwnershipError('No allow new users setting.')
    if settings.allow_new_users.allow_new_users != new_users:
        raise OwnershipError('Incorrect allow new users setting.')


def assert_users_on_whitelist(settings, users):
    if settings.HasField("user_whitelist"):
        for user in users:
            if user not in settings.user_whitelist.user_whitelist:
                raise OwnershipError(user + ' not whitelisted.')
    else:
        raise OwnershipError('No user whitelist.')


def assert_proxy_settings(settings, proxies):
    if not settings.HasField("device_proxy_settings"):
        raise OwnershipError('No proxy settings protobuf.')
    if not settings.device_proxy_settings.HasField("proxy_mode"):
        raise OwnershipError('No proxy_mode setting.')
    if settings.device_proxy_settings.proxy_mode != proxies['proxy_mode']:
        raise OwnershipError('Incorrect proxies: %s' % proxies)


NSSDB = constants.CRYPTOHOME_MOUNT_PT + '/.pki/nssdb'
PK12UTIL = 'nsspk12util'
OPENSSLP12 = 'openssl pkcs12'
OPENSSLX509 = 'openssl x509'
OPENSSLRSA = 'openssl rsa'
OPENSSLREQ = 'openssl req'
OPENSSLCRYPTO = 'openssl sha1'


def use_known_ownerkeys():
    """Sets the system up to use a well-known keypair for owner operations.

    Assuming the appropriate cryptohome is already mounted, configures the
    device to accept policies signed with the checked-in 'mock' owner key.
    """
    dirname = os.path.dirname(__file__)
    mock_keyfile = os.path.join(dirname, constants.MOCK_OWNER_KEY)
    mock_certfile = os.path.join(dirname, constants.MOCK_OWNER_CERT)
    push_to_nss(mock_keyfile, mock_certfile,  NSSDB)
    utils.open_write_close(constants.OWNER_KEY_FILE,
                           cert_extract_pubkey_der(mock_certfile))


def known_privkey():
    """Returns the mock owner private key in PEM format.
    """
    dirname = os.path.dirname(__file__)
    return utils.read_file(os.path.join(dirname, constants.MOCK_OWNER_KEY))


def known_pubkey():
    """Returns the mock owner public key in DER format.
    """
    dirname = os.path.dirname(__file__)
    return cert_extract_pubkey_der(os.path.join(dirname,
                                                constants.MOCK_OWNER_CERT))


def pairgen():
    """Generate a self-signed cert and associated private key.

    Generates a self-signed X509 certificate and the associated private key.
    The key is 2048 bits.  The generated material is stored in PEM format
    and the paths to the two files are returned.

    The caller is responsible for cleaning up these files.
    """
    keyfile = scoped_tempfile.tempdir.name + '/private.key'
    certfile = scoped_tempfile.tempdir.name + '/cert.pem'
    cmd = '%s -x509 -subj %s -newkey rsa:2048 -nodes -keyout %s -out %s' % (
        OPENSSLREQ, '/CN=me', keyfile, certfile)
    system_output_on_fail(cmd)
    return (keyfile, certfile)


def pairgen_as_data():
    """Generates keypair, returns keys as data.

    Generates a fresh owner keypair and then passes back the
    PEM-formatted private key and the DER-encoded public key.
    """
    (keypath, certpath) = pairgen()
    keyfile = scoped_tempfile(keypath)
    certfile = scoped_tempfile(certpath)
    return (utils.read_file(keyfile.name),
            cert_extract_pubkey_der(certfile.name))


def push_to_nss(keyfile, certfile, nssdb):
    """Takes a pre-generated key pair and pushes them to an NSS DB.

    Given paths to a private key and cert in PEM format, stores the pair
    in the provided nssdb.
    """
    for_push = scoped_tempfile(scoped_tempfile.tempdir.name + '/for_push.p12')
    cmd = '%s -export -in %s -inkey %s -out %s ' % (
        OPENSSLP12, certfile, keyfile, for_push.name)
    cmd += '-passin pass: -passout pass:'
    system_output_on_fail(cmd)
    cmd = '%s -d "sql:%s" -i %s -W ""' % (PK12UTIL,
                                          nssdb,
                                          for_push.name)
    system_output_on_fail(cmd)


def generate_owner_creds():
    """Generates a keypair, registered with NSS, and returns key and cert.

    Generates a fresh self-signed cert and private key.  Registers them
    with NSS and then passes back paths to files containing the
    PEM-formatted private key and certificate.
    """
    (keyfile, certfile) = pairgen()
    push_to_nss(keyfile, certfile, NSSDB)
    return (keyfile, certfile)



def cert_extract_pubkey_der(pem):
    """Given a PEM-formatted cert, extracts the public key in DER format.

    Pass in an X509 certificate in PEM format, and you'll get back the
    DER-formatted public key as a string.
    """
    outfile = scoped_tempfile(scoped_tempfile.tempdir.name + '/pubkey.der')
    cmd = '%s -in %s -pubkey -noout ' % (OPENSSLX509, pem)
    cmd += '| %s -outform DER -pubin -out %s' % (OPENSSLRSA,
                                                 outfile.name)
    system_output_on_fail(cmd)
    der = utils.read_file(outfile.name)
    return der


def generate_and_register_keypair(testuser, testpass):
    """Generates keypair, registers with NSS, sets owner key, returns keypair.

    Generates a fresh owner keypair.  Registers keys with NSS,
    puts the owner public key in the right place, ensures that the
    session_manager picks it up, ensures the owner's home dir is
    mounted, and then passes back the PEM-formatted private key and the
    DER-encoded public key.
    """
    (keypath, certpath) = generate_owner_creds()
    keyfile = scoped_tempfile(keypath)
    certfile = scoped_tempfile(certpath)

    pubkey = cert_extract_pubkey_der(certfile.name)
    utils.open_write_close(constants.OWNER_KEY_FILE, pubkey)

    cros_ui.nuke()
    cryptohome.mount_vault(testuser, testpass, create=False)
    return (utils.read_file(keyfile.name), pubkey)


def sign(pem_key, data):
    """Signs |data| with key from |pem_key|, returns signature.

    Using the PEM-formatted private key in |pem_key|, generates an
    RSA-with-SHA1 signature over |data| and returns the signature in
    a string.
    """
    sig = scoped_tempfile()
    err = scoped_tempfile()
    data_file = scoped_tempfile()
    data_file.fo.write(data)
    data_file.fo.seek(0)

    pem_key_file = scoped_tempfile(scoped_tempfile.tempdir.name + '/pkey.pem')
    utils.open_write_close(pem_key_file.name, pem_key)

    cmd = '%s -sign %s' % (OPENSSLCRYPTO, pem_key_file.name)
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
    if not sig_data:
        raise error.OwnershipError('Empty signature!')
    return sig_data
