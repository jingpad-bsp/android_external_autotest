# Copyright (c) 2011 The Chromium OS Authors. All rights reserved.
# Use of this source code is governed by a BSD-style license that can be
# found in the LICENSE file.

"""HTTP Client classes for Recall server.

This module should not be imported directly, instead the public classes
are imported directly into the top-level recall package.
"""

__all__ = ["HTTPConnection", "HTTPSConnection", "HTTPRequest", "HTTPResponse",
           "HTTPClient", "HTTPMiddleware", "ArchivingHTTPClient"]

import httplib
import logging
import struct
import threading
import time
import zlib


class HTTPResponse(httplib.HTTPResponse):
  """Recordable HTTP Response.

  Subclasses the httplib.HTTPResponse class to add the ability to record
  the data received from the server, the delay between chunks, modify data
  recevied and pickle for later playback.
  """

  logger = logging.getLogger("HTTPResponse")

  def __init__(self, *args, **kwds):
    httplib.HTTPResponse.__init__(self, *args, **kwds)
    self._mutate_functions = []
    self._decompressor = None
    self._compressor = None

  def __getstate__(self):
    state = self.__dict__.copy()
    if 'fp' in state:
      del state['fp']
    del state['_mutate_functions']
    del state['_decompressor']
    del state['_compressor']
    return state

  def __setstate__(self, state):
    self.__dict__.update(state)

    self._mutate_functions = []
    self._decompressor = None
    self._compressor = None

  @property
  def headers(self):
    """List of (header, value) tuples.

    Unlike the superclass, this doesn't merge duplicate headers since that
    breaks cookies.
    """
    if self.msg is None:
      raise httplib.ResponseNotReady()

    self._headers = []
    for line in self.msg.headers:
      sep = line.index(':')
      header = line[:sep].rstrip()
      value = line[sep+1:].lstrip().rstrip('\r\n')
      self._headers.append((header, value))

    return self._headers

  def _read_status(self):
    """Read status line from server.

    Wrapped to set the time we received the status line, which gets converted
    to a delay by HTTPConnection.getresponse()
    """
    ret = httplib.HTTPResponse._read_status(self)
    self._status_receive_time = time.time()
    return ret

  def AddMutateFunction(self, function):
    """Add a function to mutate data chunks.

    Must be called before the chunks property is accessed and before any
    headers are sent.

    Performing mutation on an HTTP Request drops the Content-Length
    header from the request, requiring the server to generate it if
    necessary. It also enforces on-the-fly decompression and
    compression of the incoming chunks,
    """
    self._mutate_functions.append(function)
    # Mutate functions means the length of the content may change;
    # server must recalculate on the fly
    del self.msg['Content-Length']

    # It also means we have to decompress and compress again after
    content_encoding = self.getheader('Content-Encoding')
    if content_encoding in ('gzip', 'deflate'):
      self.logger.debug("Will decompresss data in order to mutate")
      if content_encoding == 'gzip':
        self._decompressor = zlib.decompressobj(16 + zlib.MAX_WBITS)
        self._compressor = HTTPGzipCompressor()
      elif content_encoding == 'deflate':
        self._decompressor = zlib.decompressobj(-zlib.MAX_WBITS)
        self._compressor = zlib.compressobj()

  def _RecordChunk(self, chunk, last=False):
    """Record and mutate chunk received from the server.

    This method handles the decompression and recompression of chunks.
    """
    delay = time.time() - self.start_time
    if self._decompressor:
      chunk = self._decompressor.decompress(chunk)
    for mutate_function in self._mutate_functions:
      chunk = mutate_function(chunk)
    if self._compressor:
      chunk = self._compressor.compress(chunk)
      if last:
        chunk += self._compressor.flush(zlib.Z_FULL_FLUSH)
        chunk += self._compressor.flush()
      else:
        chunk += self._compressor.flush(zlib.Z_SYNC_FLUSH)

    self._chunks.append((delay, chunk))
    return chunk

  @property
  def chunks(self):
    """Read data chunks from server.

    This yields each chunk, including the final empty chunk in the case of
    chunked transfer-encoding and may sleep between calls to simulate the
    delay between chunk receive times.
    """
    try:
      # TODO(keybuk): this should probably record the time of the last call
      # rather than just the delay
      last_delay = 0.0
      for delay, chunk in self._chunks:
        time.sleep(delay - last_delay)
        last_delay = delay
        yield chunk
    except AttributeError:
      self._chunks = []

      # (keybuk) non-chunked we just read the entire document as one chunk;
      # this means that for streaming, there's a bit of a wait the first time
      # since it has to reach the server first, but not when playing back
      if not self.chunked:
        yield self._RecordChunk(self.read(), last=True)
        return

      # (keybuk) this code is basically _read_chunked() from the superclass,
      # simplified to always read everything, and to yield the final empty
      # chunk since we need to send it to the client ourselves
      chunk_len = None
      while chunk_len != 0:
        line = self.fp.readline()
        i = line.find(';')
        if i >= 0:
          line = line[:i] # strip chunk-extensions
        try:
          chunk_len = int(line, 16)
        except ValueError:
          # close the connection as protocol synchronisation is
          # probably lost
          self.close()
          raise httplib.IncompleteRead(''.join(value))

        # (keybuk) we always want to yield the final empty chunk since we
        # need to send it to the client anyway
        yield self._RecordChunk(self._safe_read(chunk_len), last=(chunk_len==0))
        self._safe_read(2)      # toss the CRLF at the end of the chunk

      # we read everything; close the "file"
      self.close()


class HTTPGzipCompressor(object):
  """Wrapper around zlib.Decompress to handle HTTP gzip compression.

  We can't use the Python gzip module for this since it only encapsulates
  files, and we can't subclass zlib.Decompress itself because that object
  is "hidden".

  This wrapper only implements the compress() and flush() methods, so
  is equivalent to Python 2.4-era zlib
  """

  # see gzip.py _write_gzip_header() in the Python distribution
  GZIP_HEADER = (
    '\037\213'             # magic header
    '\010'                 # compression method
    '\000'                 # flags (none)
    '\000\000\000\000'     # packed time (use zero)
    '\002'
    '\377')

  def __init__(self):
    # see gzip.py in the Python distribution
    self._compressor = zlib.compressobj(
        6, zlib.DEFLATED, -zlib.MAX_WBITS, zlib.DEF_MEM_LEVEL, 0)
    self._crc = zlib.crc32('') & 0xffffffffL
    self._size = 0
    self._sent_header = False

  def compress(self, string):
    """Compress string, returning at least part of it.

    Wraps zlib.Decompress.compress() prepending the gzip header for the
    first chunk, and keeping track of the CRC and size of the compressed
    data.

    Args:
        string: string to be compressed;
    Returns:
        string of compressed data forming at least part of string
    """
    chunk = self._compressor.compress(string)
    if not self._sent_header:
      chunk = self.GZIP_HEADER + chunk
      self._sent_header = True

    self._crc = zlib.crc32(string, self._crc) & 0xffffffffL
    self._size += len(string)
    return chunk

  def flush(self, mode=zlib.Z_FINISH):
    """Flush all pending input.

    Wraps zlib.Decompress.flush(), when called without arguments or
    with zlib.Z_FINISH, appends the CRC and size of the compressed data
    as required for gzip files.

    Args:
        mode: see zlib.py documentation
    Returns:
        string of remaining compressed data;
    """
    chunk = self._compressor.flush(mode)
    if mode == zlib.Z_FINISH:
      chunk += struct.pack('<LL', long(self._crc), long(self._size))
    return chunk


class HTTPConnectionMixIn: # HTTPConnection is not an object
  response_class = HTTPResponse

  def getresponse(self):
    """Get the response from the server.

    Wraps httplib.HTTPConnection to set the response's start_time variable
    used to caclulate the delay between chunks being received, and ensures
    that status_delay is the time it took to receive the status code line.
    """
    start_time = time.time()
    response = httplib.HTTPConnection.getresponse(self)
    response.start_time = start_time
    # calculate here since we can't set start_time before getresponse
    response.status_delay = response._status_receive_time - start_time
    return response

class HTTPConnection(HTTPConnectionMixIn, httplib.HTTPConnection):
  pass

class HTTPSConnection(HTTPConnectionMixIn, httplib.HTTPSConnection):
  pass


class HTTPRequest(object):
  """Recordable HTTP Request.

  Companion request object for HTTPResponse that is picklable and hashable
  so it can be used as a key to find the appropriate HTTPResponse object;
  implements smart matching since some headers change, and some order
  changes.

  Because of this smart matching, one HTTPRequest object may in fact match
  several recorded ones. You should therefore use an indirect lookup where
  hashing an HTTPRequest in fact yields an array of matching requests and
  their responses, and compare the request you're looking for with those
  using MatchScore()
  """

  logger = logging.getLogger("HTTPRequest")

  unmatchable_headers = [
      'Accept',
      'Accept-Charset',
      'Accept-Encoding',
      'Accept-Language',
      'Cache-Control',
      'Cookie', # special matching
      'Connection',
      'Keep-Alive',
      'Pragma',
      'Referer', # special matching
      'User-Agent',
      ]

  def __init__(self, host, command, path, headers=[], body=None, ssl=False):
    self.host = host
    self.command = command
    self.path = path
    self.headers = headers
    self.body = body
    self.ssl = ssl

    self._match_headers = self._MatchHeaders(self.headers)

  def __str__(self):
    return "%s %s://%s%s" % (self.command,
                             self.ssl and 'https' or 'http',
                             self.host, self.path)

  def __repr__(self):
    return "<%s: %s%r %s %r>" % (self.__class__.__name__,
                                 self.ssl and '(SSL) ' or '',
                                 self.host, self.command, self.path)

  def __hash__(self):
    return hash(repr((self.host, self.command, self.path, self._match_headers,
                      self.body, self.ssl)))

  def __eq__(self, other):
    if other.host != self.host:
      return False
    elif other.command != self.command:
      return False
    elif other.ssl != self.ssl:
      return False
    elif other.path != self.path:
      return False
    elif other.body != self.body:
      return False
    elif other._match_headers != self._match_headers:
      return False
    else:
      return True

  def __getstate__(self):
    state = self.__dict__.copy()
    del state['_match_headers']
    return state

  def __setstate__(self, state):
    self.__dict__.update(state)
    self._match_headers = self._MatchHeaders(state['headers'])

  @classmethod
  def _MatchHeaders(cls, headers):
    match_headers = set()
    for header, value in headers:
      header = header.title()
      if header in cls.unmatchable_headers:
        continue
      match_headers.add((header, value))
    return match_headers

  @property
  def _cookies(self):
    """Values of all cookies present in the request.

    Returns all values from all Cookie headers, including those that provide
    multiple values.
    """
    cookies = set()
    for header, value in self.headers:
      if header.title() == 'Cookie':
        for cookie in value.split(';'):
          cookies.add(cookie.strip())
    return cookies

  def getheader(self, name, default=None):
    """Retrieve value of header."""
    for header, value in self.headers:
      if header.title() == name.title():
        return value
    else:
      return default

  def MatchScore(self, other):
    """Compare request with another and return a match score.

    The hash of an HTTPRequest object may match multiple other HTTPRequest
    objects, in which case you should calculate the MatchScore of the request
    you're seeking against those present and pick the highest one.
    """
    # These numbers are randomly picked and seem to work ok for now
    score = len(self._cookies.intersection(other._cookies)) * 10
    if self.getheader('referer') == other.getheader('referer'):
      score += 1000
    return score


class HTTPClient(object):
  """Generic HTTP Client.

  This class implements an HTTP Client that fetches the results using
  the Python httplib library. HTTP Client objects are picklable.

  Example:
      client = HTTPClient()
      request = HTTPRequest('www.google.com', 'GET', '/')
      response = client(request)
  """

  def __call__(self, request):
    """Lookup the request.

    Args:
        request: HTTPRequest to lookup.

    Returns:
        HTTPResponse reply, which may include an error response.
    """
    if request.ssl:
      connection = HTTPSConnection(request.host)
    else:
      connection = HTTPConnection(request.host)

    connection.putrequest(request.command, request.path,
                          skip_host=True,
                          skip_accept_encoding=True)

    send_host = True
    send_accept_encoding = True

    for header, value in request.headers:
      if header.title() == 'Host':
        send_host = False
      elif header.title() == 'Accept-Encoding':
        send_accept_encoding = False

      connection.putheader(header, value)

    if send_host:
      connection.putheader('Host', request.host)
    if send_accept_encoding:
      connection.putheader('Accept-Encoding', '')

    connection.endheaders()

    if request.body is not None:
      connection.send(request.body)

    return connection.getresponse()


class HTTPMiddleware(object):
  """Base class for HTTP Client middleware.

  This class is a base class for HTTPClient-compatible classes that
  accept a HTTPClient argument to their constructor and surround it
  with their own processing.

  HTTP Middleware objects are picklable.

  When creating your subclass, if it will work without a HTTP Client
  you can set the client_optional class member to True; an instance
  may raise KeyError in the case where it cannot proceed further
  without one.
  """
  client_optional = False

  def __init__(self, http_client=HTTPClient()):
    """Create the client middleware instance.

    Args:
        http_client: HTTP Client object to wrap, defaults to plain HTTPClient()
            and may be None if client_optional is True for the class.
    """
    self.http_client = http_client

  @property
  def http_client(self):
    return self._http_client

  @http_client.setter
  def http_client(self, http_client):
    assert http_client is not None or self.client_optional
    self._http_client = http_client

  @http_client.deleter
  def http_client(self):
    assert self.client_optional
    self._http_client = None

  def __call__(self, request):
    """Lookup the request.

    Subclasses should override this function replacing it with their
    own, there is no need to call the superclass version.

    Args:
        request: HTTPRequest to lookup.

    Returns:
        HTTPResponse reply, which may include an error response.
    """
    if not self._http_client:
      raise KeyError

    response = self._http_client(request)
    return response


class ArchivingHTTPClient(HTTPMiddleware):
  """Archiving HTTP Client middleware.

  This HTTP Client middleware wraps an HTTP Client and archives all of its
  responses. If a request is found in the archive, that is returned in
  place of using the HTTP Client given to the constructor.

  The archive may be initialised with None as the HTTP Client in which
  case KeyError will be raised if the request is not found in the archive.

  Matching is done using HTTPRequest smart matching.
  """
  client_optional = True

  logger = logging.getLogger("ArchivingHTTPClient")

  def __init__(self, http_client=HTTPClient()):
    super(ArchivingHTTPClient, self).__init__(http_client)

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
    HTTP Client in the middleware stack to resolve it, throwing KeyError
    if no further client exists.

    Args:
        request: HTTPRequest to lookup.

    Returns:
        HTTPResponse reply, which may include an error response.
    """
    try:
      with self._lock:
        best_response, best_score = None, 0
        for original_request, response in self._responses[request]:
          score = request.MatchScore(original_request)
          if score >= best_score:
            best_response, best_score = response, score

      self.logger.info("HIT  %s", request)
      return best_response
    except KeyError:
      self.logger.info("MISS %s", request)
      if not self._http_client:
        raise

      response = self._http_client(request)
      with self._lock:
        try:
          self._responses[request].append((request, response))
        except KeyError:
          self._responses[request] = [ (request, response) ]
      return response
