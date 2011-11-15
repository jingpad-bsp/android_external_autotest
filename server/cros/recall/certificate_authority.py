# Copyright (c) 2011 The Chromium OS Authors. All rights reserved.
# Use of this source code is governed by a BSD-style license that can be
# found in the LICENSE file.

"""Certificate Authority for Recall server.

This module should not be imported directly, instead the public classes
are imported directly into the top-level recall package.
"""

__all__ = ["CertificateAuthority"]

import ConfigParser
import logging
import os
import Queue
import shutil
import subprocess
import tempfile
import threading

from cStringIO import StringIO


class CertificateAuthority(threading.Thread):
  """Certificate Authority for Recall server.

  This class implements an OpenSSL Certificate Authority for use with
  Recall, in particular the HTTPS server that utilises this class to
  generate needed certificates on the fly.

  Certificate Authority instances are picklable, the pickle will contain
  the set of requested and completed hostnames and restoring the instance
  from the pickle will create a new CA directory layout and generate
  certificates asynchronously for them.

  The authority must be initialized with a subject for the root
  certificate, e.g. "/O=Google/OU=Test". The following member variables
  are available:

    directory: location on disk of the certificate authority.
    private_key_file: location on disk of the CA private key file.
    certificate_file: location on disk of the CA certificate file.

  Certificates may be requested synchronously or asynchronously, using
  ca.GetCertificateAndPrivateKey() issues a synchronous request and the
  function will return the certificate and private keys when the
  generation is complete.

  Alternatively ca.RequestCertificateAndPrivateKey() merely begins
  generation in the background, a later call to the former method is
  required to obtain the keys by which point they will hopefully be
  generated (if not, that call blocks until they are).

  A typical use for this would be a DNSClient requesting certificate
  generation so that by the time HTTPSServer gets the files, they are
  already generated and it need not block.

  The shutdown() method of the CA must be called to clean up.
  """
  logger = logging.getLogger("CertificateAuthority")

  def __init__(self, subject, default_days=365):
    super(CertificateAuthority, self).__init__()
    self._subject = subject
    self._default_days = default_days

    self._SetupDirectory()
    self._GenerateAuthorityCertificateAndPrivateKey(self._subject)

    # We use a Queue to store the set of hostnames requested and also
    # duplicate them in the _requested set so we can quickly lookup
    # whether we need to block or queue a new incoming hostname.
    #
    # The _completed hash stores the set of generated certificates and
    # private keys, when a new certificate is added to this hash the
    # _changed Event is triggered to wake up the blockers.
    #
    # All of these structures are protected by a single lock.
    self._queue = Queue.Queue()
    self._requested = set()
    self._completed = {}
    self._lock = threading.Lock()
    self._changed = threading.Event()

    self.logger.info("Starting")
    self.daemon = True
    self.start()

  def shutdown(self):
    """Shut down the server.

    This method must be called to clean up the CA directory and shut down
    the worker thread.
    """
    # Place None in the queue to inform the thread to shutdown, and join
    # to wait for it to do so.
    self.logger.info("Shutting down")
    self._queue.put(None)
    self._queue.join()

    if hasattr(self, 'directory'):
      self._CleanupDirectory()
    else:
      self.logger.info("No directory to clean up")

  def __getstate__(self):
    state = {}
    state['subject'] = self._subject
    state['default_days'] = self._default_days
    with self._lock:
      state['certificates'] = set()
      state['certificates'].update(self._completed.keys())
      state['certificates'].update(self._requested)
    return state

  def __setstate__(self, state):
    self.__init__(state['subject'], state['default_days'])

    for hostname in state['certificates']:
      self.GetCertificateAndPrivateKey(hostname)

  def run(self):
    """Worker thread method.

    This is called by threading.Thread, it loops continuously taking new
    requests from the queue and processing them.

    Call shutdown() to stop the thread and exit.
    """
    while True:
      # Queue.get() blocks forever, we place None in the queue in
      # shutdown() to break out.
      hostname = self._queue.get(block=True)
      if hostname is None:
        self._queue.task_done()
        return

      try:
        self._ProcessRequest(hostname)
      except:
        self.logger.exception("Certificate generation failed")
      finally:
        self._queue.task_done()

  def _SetupDirectory(self):
    """Setup OpenSSL CA directory.

    Create an OpenSSL Certificate Authority directory layout, including
    the configuration file.
    """
    self.directory = tempfile.mkdtemp(prefix='CertificateAuthority')
    self.logger.info("Creating certificate authority in %s", self.directory)

    config = ConfigParser.RawConfigParser()
    config.optionxform = str

    config.add_section('ca')
    config.set('ca', 'default_ca', 'CA_default')

    config.add_section('CA_default')
    config.set('CA_default', 'dir', self.directory)

    self._certificate_dir = os.path.join(self.directory, 'certs')
    os.mkdir(self._certificate_dir, 0700)
    config.set('CA_default', 'certs', self._certificate_dir)

    crl_dir = os.path.join(self.directory, 'crl')
    os.mkdir(crl_dir, 0700)
    config.set('CA_default', 'crl_dir', crl_dir)

    newcerts_dir = os.path.join(self.directory, 'newcerts')
    os.mkdir(newcerts_dir, 0700)
    config.set('CA_default', 'new_certs_dir', newcerts_dir)

    self._private_key_dir = os.path.join(self.directory, 'private')
    os.mkdir(self._private_key_dir, 0700)

    database_file = os.path.join(self.directory, 'index.txt')
    open(database_file, 'w').close()
    config.set('CA_default', 'database', database_file)

    serial_file = os.path.join(self.directory, 'serial')
    with open(serial_file, 'w') as serialfile:
      print >>serialfile, '01'
    config.set('CA_default', 'serial', serial_file)

    self.certificate_file = os.path.join(self._certificate_dir, 'CA.pem')
    config.set('CA_default', 'certificate', self.certificate_file)

    self.private_key_file = os.path.join(self._private_key_dir, 'CA.key')
    config.set('CA_default', 'private_key', self.private_key_file)

    config.set('CA_default', 'name_opt', 'ca_default')
    config.set('CA_default', 'cert_opt', 'ca_default')

    config.set('CA_default', 'default_md', 'sha1')

    config.set('CA_default', 'policy', 'policy_anything')

    config.add_section('policy_anything')
    config.set('policy_anything', 'countryName', 'optional')
    config.set('policy_anything', 'stateOrProvinceName', 'optional')
    config.set('policy_anything', 'localityName', 'optional')
    config.set('policy_anything', 'organizationName', 'optional')
    config.set('policy_anything', 'commonName', 'supplied')
    config.set('policy_anything', 'emailAddress', 'optional')

    self._config_file = os.path.join(self.directory, 'openssl.cnf')
    with open(self._config_file, 'w') as configfile:
      config.write(configfile)

  def _CleanupDirectory(self):
    """Cleanup OpenSSL directory

    Remove the CA directory from the disk, undoes _SetupDirectory()
    """
    self.logger.info("Removing certificate authority directory")
    shutil.rmtree(self.directory)

  def _GenerateAuthorityCertificateAndPrivateKey(self, subject, days=None):
    """Generate the CA certificate and private key.

    Args:
        subject: subject for the CA key request.
        days: days key should be valid, defaults to that passed to constructor.

    Returns:
        tuple of certificate and private key filenames.
    """
    self.logger.info("Generating CA certificate and key for %s", subject)

    cmd = ('openssl', 'req', '-x509', '-newkey', 'rsa:1024', '-nodes',
           '-subj', subject,
           '-days', '%d' % (days or self._default_days),
           '-keyout', self.private_key_file,
           '-out', self.certificate_file)
    with tempfile.TemporaryFile() as output:
      try:
        subprocess.check_call(cmd, cwd=self.directory,
                              stdout=output, stderr=output)
      except subprocess.CalledProcessError:
        output.seek(0)
        self.logger.debug("openssl output:\n%s", output.read())
        raise test.TestError("Failed to generate CA certificate and key")

    os.chmod(self.private_key_file, 0400)

    return self.certificate_file, self.private_key_file

  def _GenerateCertificateRequestAndPrivateKey(self, basename, subject,
                                               days=None):
    """Generate a certificate request and private key.

    Args:
        basename: base for the filename (usually the hostname).
        subject: subject for the certificate request.
        days: days key should be valid, defaults to that passed to constructor.

    Returns:
        tuple of certificate request and private key filenames.
    """
    self.logger.info("Generate certificate request and key for %s in %s",
                     subject, basename)
    private_key_file = os.path.join(self._private_key_dir, '%s.key' % basename)
    certificate_request_file = os.path.join(self.directory, '%s.csr' % basename)

    cmd = ('openssl', 'req', '-new', '-newkey', 'rsa:1024', '-nodes',
           '-subj', subject,
           '-days', '%d' % (days or self._default_days),
           '-keyout', private_key_file,
           '-out', certificate_request_file)
    with tempfile.TemporaryFile() as output:
      try:
        subprocess.check_call(cmd, cwd=self.directory,
                              stdout=output, stderr=output)
      except subprocess.CalledProcessError:
        output.seek(0)
        self.logger.debug("openssl output:\n%s", output.read())
        raise test.TestError("Failed to generate certificate request for %s",
                             subject)

    os.chmod(self.private_key_file, 0400)

    return certificate_request_file, private_key_file

  def _SignCertificateRequest(self, certificate_request_file, days=None):
    """Sign certificate request file.

    Args:
        certificate_request_file: filename of certificate request.
        days: days certificate should be valid, defaults to that passed to
              constructor.

    Returns:
        filename of certificate.
    """
    basename = os.path.splitext(os.path.basename(certificate_request_file))[0]
    self.logger.info("Signing certificate request for %s", basename)

    certificate_file = os.path.join(self._certificate_dir, '%s.pem' % basename)

    cmd = ('openssl', 'ca', '-config', self._config_file, '-batch',
           '-days', '%d' % (days or self._default_days),
           '-out', certificate_file,
           '-in', certificate_request_file)
    with tempfile.TemporaryFile() as output:
      try:
        subprocess.check_call(cmd, cwd=self.directory,
                              stdout=output, stderr=output)
      except subprocess.CalledProcessError:
        output.seek(0)
        self.logger.debug("openssl output:\n%s", output.read())
        raise test.TestError("Failed to sign certificate for %s", basename)

    return certificate_file

  def _GenerateCertificateAndPrivateKey(self, basename, subject, days=None):
    """Generate a certificate and private key.

    Args:
        basename: base for the filename (usually the hostname).
        subject: subject for the certificate.
        days: days key should be valid, defaults to that passed to constructor.

    Returns:
        tuple of certificate and private key filenames.
    """
    certificate_request_file, private_key_file = \
        self._GenerateCertificateRequestAndPrivateKey(basename, subject,
                                                      days=days)
    try:
      certificate_file = self._SignCertificateRequest(
          certificate_request_file, days=days)
    except:
      os.unlink(private_key_file)
      raise
    finally:
      os.unlink(certificate_request_file)

    return certificate_file, private_key_file

  def RequestCertificateAndPrivateKey(self, hostname):
    """Asynchronously request generation of certificate and private key.

    This method returns immediately while the certificate and private key
    are generated in the background by the worker thread, or if a
    certificate and private key already exist for the hostname given.

    To request the filenames, call GetCertificateAndPrivateKey()

    Args:
        hostname: hostname required.
    """
    with self._lock:
      if hostname in self._requested \
            or hostname in self._completed:
        return

      self._requested.add(hostname)
      self._queue.put(hostname)

  def GetCertificateAndPrivateKey(self, hostname):
    """Retrieve certificate and private key.

    Makes a synchronous request to obtain a certificate and private key
    for the hostname given. If they have already been generated, for
    example by a prior call to this method or to the
    RequestCertificateAndPrivateKey() method, this returns immediately.

    Otherwise this function will block until the worker thread has
    generated the necessary keys, which may take some time depending
    on available entropy.

    Args:
        hostname: hostname required.

    Returns:
        tuple of certificate and private key filenames.
    """
    while True:
      with self._lock:
        if hostname in self._completed:
          certificate_file, private_key_file = self._completed[hostname]
          return certificate_file, private_key_file
        elif hostname not in self._requested:
          self._requested.add(hostname)
          self._queue.put(hostname)

      # Wait for the _completed hash to change, and clear the event when
      # it does. All threads are woken up simultaneously for each change.
      self._changed.wait()
      self._changed.clear()

  def _ProcessRequest(self, hostname):
    """Process a request.

    Called from the worker thread to process a request, generates the
    certificate request and private key, and then signs the request,
    before placing the respective keys into the _completed hash and
    waking up all threads.

    Args:
        hostname: hostname requested.
    """
    self.logger.debug("Received request for %s", hostname)
    subject = "/CN=%s" % hostname

    (certificate_file, private_key_file) \
        = self._GenerateCertificateAndPrivateKey(hostname, subject)

    with self._lock:
      self._completed[hostname] = (certificate_file, private_key_file)
      self._requested.remove(hostname)

    self.logger.debug("Request for %s completed", hostname)
    self._changed.set()
