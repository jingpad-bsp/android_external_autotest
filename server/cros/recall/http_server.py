# Copyright (c) 2011 The Chromium OS Authors. All rights reserved.
# Use of this source code is governed by a BSD-style license that can be
# found in the LICENSE file.

"""HTTP Server classes for Recall server.

This module should not be imported directly, instead the public classes
are imported directly into the top-level recall package.
"""

__all__ = ["HTTPServer", "HTTPSServer", "HTTPRequestHandler"]

import BaseHTTPServer
import fnmatch
import httplib
import logging
import SocketServer
import ssl
import tempfile
import threading

import socket_util
from certificate_authority import CertificateAuthority
from dns_client import DNSRequest, DNSClient
from http_client import HTTPRequest, HTTPClient


def _GetHostnameForAddress(dns_client, address):
  """Get the hostname for an address.

  Utility function that uses a DNS Client to perform a reverse lookup
  and returns the hostname without trailing periods.
  """
  for hostname in dns_client(DNSRequest.ReverseLookup(address)):
    return hostname.text.rstrip('.')
  else:
    return None


class HTTPServer(SocketServer.ThreadingMixIn,
                 BaseHTTPServer.HTTPServer,
                 threading.Thread):
  """Simple multithreaded HTTP Server.

  This class implements a multithreaded HTTP Server that uses the HTTP Client
  passed to the constructor to resolve requests. For consistency with the
  HTTPSServer class, the constructor also accepts DNS Client and
  Certificate Authority arguments, though these will not be used.

  The shutdown() method must be called to clean up.
  """
  logger = logging.getLogger("HTTPServer")

  ssl = False

  def __init__(self, server_address,
               http_client=HTTPClient(),
               dns_client=DNSClient(),
               certificate_authority=None):
    BaseHTTPServer.HTTPServer.__init__(self, server_address, HTTPRequestHandler)
    self.request_queue_size = 128

    threading.Thread.__init__(self, target=self.serve_forever)

    self.http_client = http_client
    self.dns_client = dns_client
    self.certificate_authority = certificate_authority

    self.logger.info("Starting on %s", self.server_address)
    self.daemon = True
    self.start()

  def shutdown(self):
    """Shutdown the server."""
    self.logger.info("Shutting down")
    super(HTTPServer, self).shutdown()


class HTTPSServer(SocketServer.ThreadingMixIn,
                  BaseHTTPServer.HTTPServer,
                  threading.Thread):
  """Multithreaded HTTPS Server.

  This class implements a multithreaded HTTPS Server that uses the HTTP Client
  passed to the constructor to resolve requests. The original destination
  address of incoming connections is resolved to a hostname using the passed
  DNS Client, and a certificate generated using the passed Certificate
  Authority.

  For best results, the DNS Client should be the SymmetricDNSClient class.

  The shutdown() method must be called to clean up.
  """
  logger = logging.getLogger("HTTPSServer")

  ssl = True

  def __init__(self, server_address,
               http_client=HTTPClient(),
               dns_client=DNSClient(),
               certificate_authority=None):
    BaseHTTPServer.HTTPServer.__init__(self, server_address, HTTPRequestHandler)
    self.request_queue_size = 128

    threading.Thread.__init__(self, target=self.serve_forever)

    self.http_client = http_client
    self.dns_client = dns_client
    self.certificate_authority = certificate_authority

    self.logger.info("Starting on %s", self.server_address)
    self.daemon = True
    self.start()

  def shutdown(self):
    """Shutdown the server."""
    self.logger.info("Shutting down")
    super(HTTPSServer, self).shutdown()

  def get_request(self):
    """Accept incoming request.

    Looks up the original destination of the address and resolves that to
    a hostname using the DNS Client passed to the constructor. Certificates
    and Private Keys are obtained from the class Certificate Authority,
    and each connection is individually wrapped through SSL.
    """
    (conn, address) = self.socket.accept()
    self.logger.debug("Accepted request from %s:%d", address[0], address[1])

    try:
      original_address, original_port \
          = socket_util.GetOriginalDestinationAddress(conn)

      certificate_hostname = _GetHostnameForAddress(self.dns_client,
                                                    original_address)
      if certificate_hostname is None:
        certificate_hostname = original_address

      self.logger.debug("Original destination %s:%d; using certificate for %s",
                        original_address, original_port, certificate_hostname)
    except (TypeError, KeyError):
      certificate_hostname = self.server_name
      self.logger.warn("Using our own certificate for this request")

    (certificate_file, private_key_file) = \
        self.certificate_authority.GetCertificateAndPrivateKey(
            certificate_hostname)

    return (ssl.wrap_socket(conn, server_side=True,
                            certfile=certificate_file,
                            keyfile=private_key_file),
            address)


class HTTPRequestHandler(BaseHTTPServer.BaseHTTPRequestHandler):
  """Request handler for HTTP and HTTPS Servers.

  Handles incoming HTTP requests on behalf of HTTPServer and HTTPSServer
  (distinguished by their ssl members). The request is converted to an
  HTTPRequest object and a response obtained from the server's http_client
  member before being sent back to the client.

  Additionally if the incoming request is directed at the server itself,
  the first element of the path may be a function local to this class in
  which case it is run to generate the response.
  """

  protocol_version = 'HTTP/1.1'

  # Turn on buffering, we explicitly flush where we need to
  wbufsize = -1

  def __init__(self, request, client_address, server):
    self.logger = logging.getLogger("HTTPRequestHandler:%s:%d"
                                   % (client_address[0], client_address[1]))

    BaseHTTPServer.BaseHTTPRequestHandler.__init__(
        self, request, client_address, server)

  def log_request(self, code='-', size='-'):
    # we do our own request logging
    pass

  # reformat other log messages to our own logger
  def log_error(self, format, *args):
    self.logger.error(format, *args)
  def log_message(self, format, *args):
    self.logger.info(format, *args)

  # handle all methods the same way
  def do_HEAD(self):
    self._HandleRequest()
  def do_GET(self):
    self._HandleRequest()
  def do_POST(self):
    self._HandleRequest()

  def _RequestIsForSelf(self):
    """Check whether the request is for our server name or IP Address.

    Returns:
        True if request is for us, False otherwise.
    """
    server_aliases = [ self.server.server_name, self.request.getsockname()[0] ]
    try:
      sep = self.server.server_name.index('.')
      server_aliases.append(self.server.server_name[:sep])
    except ValueError:
      pass

    return self.host.split(':')[0] in server_aliases

  def _HandleRequest(self):
    """Handle the request."""
    # Lookup the hostname
    self.host = self.headers.get('host', None)
    if not self.host:
      try:
        original_address, original_port \
            = socket_util.GetOriginalDestinationAddress(self.request)

        hostname = _GetHostnameForAddress(self.server.dns_client,
                                          original_address)
        if hostname:
          self.host = '%s:%d' % (hostname, original_port)
        else:
          self.host = '%s:%d' % (original_address, original_port)

        self.logger.debug("Missing Host header in request, used %s", self.host)
      except TypeError:
        return self._Error("Missing Host header in request, "
                           "and can't obtain original destination")

    # Handle requests for our own host
    if self._RequestIsForSelf():
      command = self.path[1:].split('/')
      try:
        return getattr(self, command[0])(*command[1:])
      except AttributeError:
        return self._Error("Unknown command %s" % command[0])
      except TypeError, e:
        return self._Error(str(e))

    content_length = int(self.headers.get('Content-Length', 0))
    if content_length:
      body = self.rfile.read(content_length)
    else:
      body = None

    request = HTTPRequest(self.host, self.command, self.path,
                          self.headers.items(), body,
                          self.server.ssl)

    try:
      response = self.server.http_client(request)
    except KeyError:
      return self._Error("Not found in archive", 404)

    if response.version == 10:
      self.protocol_version = 'HTTP/1.0'
    self.send_response(response.status, response.reason)

    sent_content_length = False
    for header, value in response.headers:
      self.send_header(header, value)
      if header.title() == 'Content-Length':
        sent_content_length = True

    # Sometimes we need to send the content-length header ourselves; in those
    # cases delay ending the headers until we receive the data from the server
    if response.chunked or sent_content_length:
      self.end_headers()
      self.wfile.flush()
    else:
      self.logger.debug("Will send Content-Length later")

    for chunk in response.chunks:
      if response.chunked:
        self.wfile.write('%x\r\n%s\r\n' % (len(chunk), chunk))
      else:
        if not sent_content_length:
          self.send_header('Content-Length', str(len(chunk)))
          self.end_headers()
          sent_content_length = True
        self.wfile.write(chunk)
      self.wfile.flush()

    # Should never happen, but let's be careful
    if not response.chunked and not sent_content_length:
      self.logger.debug("Handled empty request")
      self.send_header('Content-Length', '0')
      self.end_headers()
      self.wfile.flush()

    if response.version == 10:
      self.close_connection = 1

  def GetRootCertificate(self):
    """Generate a response with the CA's certificate.

    Command intended for use by clients, writes back the attached CA's
    root certificate.
    """
    with open(self.server.certificate_authority.certificate_file) \
          as cert:
      certificate = cert.read()

    self.send_response(httplib.OK)
    self.send_header('Content-Type', 'text/plain')
    self.send_header('Content-Length', str(len(certificate)))
    self.end_headers()
    self.wfile.write(certificate)
    self.wfile.flush()

  def _Error(self, message, code=httplib.INTERNAL_SERVER_ERROR):
    """Reply with an error.

    Generates an error reply and returns it to the client.
    """
    self.logger.warn(message)

    self.send_response(code)
    self.send_header('Content-Type', 'text/plain')
    self.send_header('Content-Length', str(len(message)))
    self.end_headers()
    self.wfile.write(message)
    self.wfile.flush()
