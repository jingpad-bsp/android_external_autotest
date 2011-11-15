# Copyright (c) 2011 The Chromium OS Authors. All rights reserved.
# Use of this source code is governed by a BSD-style license that can be
# found in the LICENSE file.

"""DNS Server classes for Recall server.

This module should not be imported directly, instead the public classes
are imported directly into the top-level recall package.
"""

__all__ = ["DNSServer", "DNSRequestHandler"]

import logging
import SocketServer
import threading

import dns.flags
import dns.message
import dns.opcode
import dns.rdataclass
import dns.rdatatype
import dns.rrset

from dns_client import DNSRequest, DNSClient


class DNSServer(SocketServer.ThreadingUDPServer,
                threading.Thread):
  """Simple multithreaded DNS Server.

  This class implements a multithreaded DNS Server that uses the DNS Client
  passed to the constructor to resolve requests.

  The shutdown() method must be called to clean up.
  """
  logger = logging.getLogger("DNSServer")

  def __init__(self, server_address,
               dns_client=DNSClient()):
    SocketServer.ThreadingUDPServer.__init__(self, server_address,
                                             DNSRequestHandler)
    self.request_queue_size = 128

    threading.Thread.__init__(self, target=self.serve_forever)

    self.dns_client = dns_client

    self.logger.info("Starting on %s", self.server_address)
    self.daemon = True
    self.start()

  def shutdown(self):
    """Shutdown the server."""
    self.logger.info("Shutting down")
    super(DNSServer, self).shutdown()


class DNSRequestHandler(SocketServer.DatagramRequestHandler):
  """Request handler for DNS Server.

  Handles incoming DNS requests on behalf of DNSServer; the request
  is converted to a DNSRequest object and a response obtained from the
  DNSServer's dns_client member before being converted back to a
  dnspython object and written to the client.
  """
  logger = logging.getLogger("DNSRequestHandler")

  def _Error(self, query, opcode=dns.rcode.NOTIMP):
    """Generate an Error response.

    Generates and writes back an error response.

    Args:
        query: query to respond to.
        opcode: dns.rcode.* member for error type.
    """
    response = dns.message.make_response(query)
    response.flags |= dns.flags.RA | dns.flags.AA
    response.set_rcode(opcode)
    self.wfile.write(response.to_wire())

  def handle(self):
    """Handle the request."""
    query = dns.message.from_wire(self.rfile.read())

    if query.opcode() != dns.opcode.QUERY:
      self.logger.debug("Ignored unhandled DNS message type: %s",
                        dns.opcode.to_text(query.opcode))
      return self._Error(query)

    if len(query.question) > 1:
      self.logger.debug("Ignored additional questions in DNS message")
    if query.question[0].rdclass != dns.rdataclass.IN:
      self.logger.debug("Ignored unhandled DNS query class: %s",
                        dns.rdataclass.to_text(query.question[0].rdlcass))
      return self._Error(query)
    if query.question[0].rdtype != dns.rdatatype.A \
          and query.question[0].rdtype != dns.rdatatype.PTR:
      if query.question[0].rdtype != dns.rdatatype.AAAA: # IPv6 is hard
        self.logger.debug("Ignored unhandled DNS query type: %s",
                          dns.rdatatype.to_text(query.question[0].rdtype))

      return self._Error(query)

    reply = dns.message.make_response(query)
    reply.flags |= dns.flags.RA | dns.flags.AA

    request = DNSRequest(query.question[0].name,
                         query.question[0].rdtype, query.question[0].rdclass)

    try:
      for response in self.server.dns_client(request):
        reply.answer.append(dns.rrset.from_text(
            query.question[0].name,
            3600,
            query.question[0].rdclass,
            query.question[0].rdtype,
            response.text))
      if not len(reply.answer):
        reply.set_rcode(dns.rcode.NXDOMAIN)
    except KeyError:
      reply.set_rcode(dns.rcode.NXDOMAIN)

    self.wfile.write(reply.to_wire())
