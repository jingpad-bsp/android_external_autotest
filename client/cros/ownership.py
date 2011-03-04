# Copyright (c) 2011 The Chromium OS Authors. All rights reserved.
# Use of this source code is governed by a BSD-style license that can be
# found in the LICENSE file.

import logging, os, tempfile
from autotest_lib.client.bin import utils
from autotest_lib.client.common_lib import autotemp, error
import common
import constants, cryptohome, login


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


NSSDB = constants.CRYPTOHOME_MOUNT_PT + '/.pki/nssdb'
PK12UTIL = 'nsspk12util'
OPENSSLP12 = 'openssl pkcs12'
OPENSSLX509 = 'openssl x509'
OPENSSLRSA = 'openssl rsa'
OPENSSLREQ = 'openssl req'
OPENSSLCRYPTO = 'openssl sha1'


def pairgen():
    """Generate a self-signed cert and associated private key.

    Generates a self-signed X509 certificate and the associated private key.
    The key is 2048 bits.  The generated material is stored in PEM format
    and the paths to the two files are returned.

    The caller is responsible for cleaning up these files.
    """
    keyfile = scoped_tempfile.tempdir.name + 'private.key'
    certfile = scoped_tempfile.tempdir.name + 'cert.pem'
    cmd = '%s -x509 -subj %s -newkey rsa:2048 -nodes -keyout %s -out %s' % (
        OPENSSLREQ, '/CN=me', keyfile, certfile)
    system_output_on_fail(cmd)
    return (keyfile, certfile)


def push_to_nss(keyfile, certfile, nssdb):
    """Takes a pre-generated key pair and pushes them to an NSS DB.

    Given paths to a private key and cert in PEM format, stores the pair
    in the provided nssdb.
    """
    for_push = scoped_tempfile(scoped_tempfile.tempdir.name + 'for_push.p12')
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
    outfile = scoped_tempfile(scoped_tempfile.tempdir.name + 'pubkey.der')
    cmd = '%s -in %s -pubkey -noout ' % (OPENSSLX509, pem)
    cmd += '| %s -outform DER -pubin -out %s' % (OPENSSLRSA,
                                                 outfile.name)
    system_output_on_fail(cmd)
    der = utils.read_file(outfile.name)
    return der


def generate_and_register_owner_keypair(testuser, testpass):
    """Generates keypair, registers with NSS, sets owner key, returns pkey.

    Generates a fresh owner keypair.  Registers keys with NSS,
    puts the owner public key in the right place, ensures that the
    session_manager picks it up, ensures the owner's home dir is
    mounted, and then passes back paths to a file containing the
    PEM-formatted private key.
    """
    (keyfile, certfile) = generate_owner_creds()
    utils.open_write_close(constants.OWNER_KEY_FILE,
                           cert_extract_pubkey_der(certfile))
    login.refresh_login_screen()
    cryptohome.mount_vault(testuser, testpass, create=False)
    return keyfile


def sign(pem_key_file, data):
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

    cmd = '%s -sign %s' % (OPENSSLCRYPTO, pem_key_file)
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
        raise error.TestFail('Empty signature!')
    return sig_data

