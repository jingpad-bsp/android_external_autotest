# Copyright (c) 2011 The Chromium OS Authors. All rights reserved.
# Use of this source code is governed by a BSD-style license that can be
# found in the LICENSE file.

"""DNS Client classes for Recall server.

This module should not be imported directly, instead the public classes
are imported directly into the top-level recall package.
"""

__all__ = ["DNSRequest", "DNSResponse", "DNSClient", "DNSMiddleware",
           "ArchivingDNSClient", "SymmetricDNSClient"]

import logging
import socket
import struct
import threading

import dns.rdataclass
import dns.rdatatype
import dns.resolver


class DNSMessage(object):
  """Simple DNS Message object base class.

  This class encapsulates the relatively complicated API of dnspython
  into an instance that holds the relevant parts of a message together
  and implements matching and hashing.

  DNS Message objects are picklable.

  Generally you instantiate either the DNSRequest or DNSResponse objects
  rather than this base class.
  """
  def __init__(self, text, rdtype=dns.rdatatype.A, rdclass=dns.rdataclass.IN):
    """Create a DNS Message.

    Args:
        text: text content of the record, e.g. IP address or hostname.
        rdtype: data type of record, use a dns.rdatatype.* constant.
        rdclass: data class of record, use a dns.rdataclass.* constant.
    """
    try:
      self.text = text.to_text()
    except AttributeError:
      self.text = text
    self.rdtype = rdtype
    self.rdclass = rdclass

  def __str__(self):
    return "%s %s %s" % (dns.rdataclass.to_text(self.rdclass),
                         dns.rdatatype.to_text(self.rdtype),
                         self.text)

  def __repr__(self):
    return "<%s: %s>" % (self.__class__.__name__, str(self))

  def __hash__(self):
    return hash(repr((self.text, self.rdtype, self.rdclass)))

  def __eq__(self, other):
    if other.text != self.text:
      return False
    elif other.rdtype != self.rdtype:
      return False
    elif other.rdclass != self.rdclass:
      return False
    else:
      return True

  def IsAddress(self):
    """Return whether this is an address message.

    Returns:
        True if the data class/type is IN A; for a Request that means this
        is True for a request for an IP Address (ie. a hostname lookup),
        for a Response that means this is True for a response containing
        an IP Address for a hostname.

        False otherwise.
    """
    return self.rdclass == dns.rdataclass.IN \
        and self.rdtype == dns.rdatatype.A

  def IsName(self):
    """Return whether this is a name message.

    Returns:
        True if the data class/type is IN PTR; for a Request that means this
        is True for a request for a hostname (ie. a reverse lookup), for a
        Response that means this is True for a response containing a
        hostname for an IP Address.

        False otherwise.
    """
    return self.rdclass == dns.rdataclass.IN \
        and self.rdtype == dns.rdatatype.PTR


class DNSRequest(DNSMessage):
  """Simple DNS Request object.

  Encapsulates a DNS Request.
  """
  @classmethod
  def ReverseLookup(cls, address):
    """Create a DNS Request for a reverse lookup.

    This class method constructor creates a DNSRequest object for a
    given IP address that results in a reverse lookup.

    i.e. DNSRequest.ReverseLookup('192.168.1.1') results in an instance
    of <DNSRequest IN PTR 1.1.168.192.in-addr.arpa>

    Args:
        address: IP address in usual dotted form.

    Returns:
        newly created DNSRequest object.
    """
    text = '.'.join(reversed(address.split('.'))) + '.in-addr.arpa'
    return cls(text, dns.rdatatype.PTR, dns.rdataclass.IN)


class DNSResponse(DNSMessage):
  """Simple DNS Response object.

  Encapsulates a DNS Response.
  """
  pass


class DNSClient(object):
  """DNS Client for system resolver.

  This class implements a DNS Client that uses the system resolver to
  lookup the responses for DNSRequest objects. DNS Client objects are
  picklable.

  Example:
      client = DNSClient()
      request = DNSRequest('www.google.com')
      for response in client(request):
        ...
  """
  def __init__(self):
    self._resolver = dns.resolver.get_default_resolver()

  def __getstate__(self):
    state = self.__dict__.copy()
    del state['_resolver']
    return state

  def __setstate__(self):
    self.__dict__.update(state)

    self._resolver = dns.resolver.get_default_resolver()

  def __call__(self, request):
    """Lookup the request.

    Args:
        request: DNSRequest to lookup.

    Yields:
        DNSResponse for each reply. No responses are yielded for NXDOMAIN.
    """
    try:
      for answer in self._resolver.query(request.text,
                                         request.rdtype, request.rdclass):
        if answer.rdclass == dns.rdataclass.IN \
              and answer.rdtype == dns.rdatatype.A:
          text = answer.address
        elif answer.rdtype == dns.rdatatype.PTR:
          text = answer.target.to_text()
        else:
          continue

        yield DNSResponse(text, answer.rdtype, answer.rdclass)
    except dns.resolver.NXDOMAIN:
      return


class DNSMiddleware(object):
  """Base class for DNS Client middleware.

  This class is a base class for DNSClient-compatible classes that
  accept a DNSClient argument to their constructor and surround it
  with their own processing.

  DNS Middleware options are picklable.

  When creating your subclass, if it will work without a DNS Client
  you can set the client_optional class member to True; an instance
  may raise KeyError in the case where it cannot proceed further
  without one.
  """
  client_optional = False

  def __init__(self, dns_client=DNSClient()):
    """Create the client middleware instance.

    Args:
        dns_client: DNS Client object to wrap, defaults to plain DNSClient()
            and may be None if client_optional is True for the class.
    """
    self.dns_client = dns_client

  @property
  def dns_client(self):
    return self._dns_client

  @dns_client.setter
  def dns_client(self, dns_client):
    assert dns_client is not None or self.client_optional
    self._dns_client = dns_client

  @dns_client.deleter
  def dns_client(self):
    assert self.client_optional
    self._dns_client = None

  def __call__(self, request):
    """Lookup the request.

    Returns an archived response if one exists, otherwise uses the next
    DNS Client in the middleware stack to resolve it, throwing KeyError
    if no further client exists.

    Subclasses should override this function replacing it with their
    own, there is no need to call the superclass version.

    Args:
        request: DNSRequest to lookup.

    Yields:
        DNSResponse for each reply. No responses are yielded for NXDOMAIN.
    """
    if not self._dns_client:
      raise KeyError

    responses = self._dns_client(request)
    for response in responses:
      yield response


class ArchivingDNSClient(DNSMiddleware):
  """Archiving DNS Client middleware.

  This DNS Client middleware wraps a DNS Client and archives all of its
  responses. If a request is found in the archive, that is returned in
  place of using the DNS Client given to the constructor.

  The archive may be initialised with None as the DNS Client in which
  case KeyError will be raised if the request is not found in the archive.

  When using an HTTPS Server you should use SymmetricDNSClient instead.
  """
  client_optional = True

  logger = logging.getLogger("ArchivingDNSClient")

  def __init__(self, dns_client=DNSClient()):
    super(ArchivingDNSClient, self).__init__(dns_client)

    self._responses = {}
    self._lock = threading.Lock()

  def __getstate__(self):
    state = self.__dict__.copy()
    del state['_lock']
    return state

  def __setstate__(self, state):
    self.__dict__.update(state)

    self._lock = threading.Lock()

  def __call__(self, request):
    """Lookup the request.

    Returns an archived response if one exists, otherwise uses the next
    DNS Client in the middleware stack to resolve it, throwing KeyError
    if no further client exists.

    Args:
        request: DNSRequest to lookup.

    Yields:
        DNSResponse for each reply. No responses are yielded for NXDOMAIN.
    """
    try:
      with self._lock:
        for response in self._responses[request]:
          yield response
      self.logger.info("HIT  %s", request)
    except KeyError:
      self.logger.info("MISS %s", request)
      if not self._dns_client:
        raise

      responses = self._dns_client(request)
      with self._lock:
        self._responses[request] = []
        for response in responses:
          self._responses[request].append(response)
          yield response


class SymmetricDNSClient(DNSMiddleware):
  """Symmetric DNS Client middleware.

  This DNS Client middleware wraps a DNS Client and ensures that all
  responses are symmetric. I.e. a request for www.google.com will always
  return the same IP Address, eliding any multiple responses, and
  conversely no other request will return that same IP Address even if
  it could potentially resolve.

  The symmetricness allows the HTTPS Server to translate a destination
  IP Address to only one possible hostname for certificate generation.

  In the case where two hostnames resolve to only one IP Address, the
  second to be looked up is given a fake IP Address in the 10/8 range.

  An archive is kept of all responses and the class may be initialised
  with None as the DNS Client in which case KeyError will be raised if
  the request is not found in the archive.
  """
  client_optional = True

  logger = logging.getLogger("SymmetricDNSClient")

  def __init__(self, dns_client=DNSClient()):
    super(SymmetricDNSClient, self).__init__(dns_client)

    self._hostnames = {}
    self._addresses = {}
    self._reserve_addr = 0x0a000000
    self._lock = threading.Lock()

  def __getstate__(self):
    state = self.__dict__.copy()
    del state['_lock']
    return state

  def __setstate__(self, state):
    self.__dict__.update(state)

    self._lock = threading.Lock()

  def __call__(self, request):
    """Lookup the request.

    Returns an archived response if one exists, otherwise uses the next
    DNS Client in the middleware stack to resolve it, throwing KeyError
    if no further client exists.

    Args:
        request: DNSRequest to lookup.

    Yields:
        Single DNSResponse for the reply.
        No responses are yielded for NXDOMAIN.
    """
    if request.IsAddress():
      responses = self._LookupAddress(request)
    elif request.IsName():
      responses = self._LookupName(request)
    else:
      if not self._dns_client:
        raise KeyError

      self.logger.info("Fallback for request %s", request)
      responses = self._dns_client(request)

    for response in responses:
      yield response

  def _LookupAddress(self, request):
    """Lookup an address request.

    Translates a hostname into an IP Address, where this is the first
    lookup for either, uses the next DNS Client in the stack to obtain
    a real answer.

    Ideally the first IP Address from the real answer that has not already
    been returned for a different hostname is used. In the case where all
    addresses from the real reply have been returned for other hostnames,
    a fake IP address in the 10/8 range is returned.

    Args:
        request: DNSRequest to lookup.

    Yields:
        Single DNSResponse for the reply.
        No responses are yielded for NXDOMAIN.
    """
    hostname = request.text.rstrip('.')

    try:
      with self._lock:
        address = self._addresses[hostname]
      self.logger.info("HIT  %s -> %s", hostname, address)
    except KeyError:
      if not self._dns_client:
        self.logger.info("MISS  %s -> (no record)", hostname)
        raise

      responses = self._dns_client(request)
      with self._lock:
        nxdomain = True
        for response in responses:
          nxdomain = False

          if response.IsAddress():
            address = response.text
            if address not in self._hostnames:
              self.logger.info("MISS  %s -> %s (using client)",
                               hostname, address)
              break
        else:
          if nxdomain:
            address = None
            self.logger.info("MISS  %s -> NXDOMAIN", hostname)
          else:
            addr = self._reserve_addr = self._reserve_addr + 1
            address = socket.inet_ntoa(struct.pack('!I', addr))
            self.logger.info("MISS  %s -> %s (synthesised)", hostname, address)

        self._addresses[hostname] = address
        if address is not None:
          self._hostnames[address] = hostname
    if address is not None:
      yield DNSResponse(address, dns.rdatatype.A, dns.rdataclass.IN)

  def _LookupName(self, request):
    """Lookup a hostname request.

    Translates an IP Address into a hostname, where this is the first
    lookup for either, uses the next DNS Client in the stack to obtain
    a real answer.

    The hostname/address pair is recorded so that a forward lookup for
    the address of the hostname always returns the same result. If the
    hostname has returned a different address previously, NXDOMAIN is
    simulated for this lookup.

    Args:
        request: DNSRequest to lookup.

    Yields:
        Single DNSResponse for the reply.
        No responses are yielded for NXDOMAIN.
    """
    in_addr = '.in-addr.arpa'
    self.logger.debug('LookupName %r', request)
    assert request.text.rstrip('.').endswith(in_addr)
    address = '.'.join(
        reversed(request.text.rstrip('.')[:-len(in_addr)].split('.')))

    try:
      with self._lock:
        hostname = self._hostnames[address]
      self.logger.info("HIT  %s -> %s", address, hostname)
    except KeyError:
      if not self._dns_client:
        self.logger.info("MISS  %s -> (no record)", address)
        raise

      responses = self._dns_client(request)
      with self._lock:
        for response in responses:
          if response.IsName():
            hostname = response.text.rstrip('.')
            if hostname not in self._addresses:
              self.logger.info("MISS  %s -> %s (using client)",
                               address, hostname)
              break
        else:
          hostname = None
          self.logger.info("MISS  %s -> NXDOMAIN", address)

        self._hostnames[address] = hostname
        if hostname is not None:
          self._addresses[hostname] = address
    if hostname is not None:
      yield DNSResponse(hostname + '.', dns.rdatatype.PTR, dns.rdataclass.IN)
