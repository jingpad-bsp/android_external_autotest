# Copyright 2018 The Chromium OS Authors. All rights reserved.
# Use of this source code is governed by a BSD-style license that can be
# found in the LICENSE file.

import BaseHTTPServer
import base64
import binascii
import thread
import urlparse
from xml.dom import minidom

def _split_url(url):
    """Splits a URL into the URL base and path."""
    split_url = urlparse.urlsplit(url)
    url_base = urlparse.urlunsplit(
            (split_url.scheme, split_url.netloc, '', '', ''))
    url_path = split_url.path
    return url_base, url_path.lstrip('/')


class NanoOmahaDevserver(object):
    """A simple Omaha instance that can be setup on a DUT in client tests."""

    def __init__(self, eol=False, failures_per_url=1, backoff=False,
                 num_urls=2):
        """
        Create a nano omaha devserver.

        @param eol: True if we should return a response with _eol flag.
        @param failures_per_url: how many times each url can fail.
        @param backoff: Whether we should wait a while before trying to
                        update again after a failure.
        @param num_urls: The number of URLs in the omaha response.

        """
        self._eol = eol
        self._failures_per_url = failures_per_url
        self._backoff = backoff
        self._num_urls = num_urls


    class Handler(BaseHTTPServer.BaseHTTPRequestHandler):
        """Inner class for handling HTTP requests."""

        _OMAHA_RESPONSE_TEMPLATE_HEAD = """
          <response protocol=\"3.0\">
            <daystart elapsed_seconds=\"44801\"/>
            <app appid=\"%s\" status=\"ok\">
              <ping status=\"ok\"/>
              <updatecheck status=\"ok\">
                <urls>
        """
        _OMAHA_RESPONSE_BODY = """
                </urls>
                <manifest version=\"9999.0.0\">
                  <packages>
                    <package hash_sha256=\"%s\" name=\"%s\" size=\"%d\"
                    required=\"true\"/>
                  </packages>
                  <actions>
                    <action event=\"postinstall\"
              ChromeOSVersion=\"9999.0.0\"
              sha256=\"%s\"
              needsadmin=\"false\"
              IsDeltaPayload=\"%s\"
              MaxFailureCountPerUrl=\"%d\"
              DisablePayloadBackoff=\"%s\"
        """

        _OMAHA_RESPONSE_TEMPLATE_TAIL = """ />
                  </actions>
                </manifest>
              </updatecheck>
            </app>
          </response>
        """

        _OMAHA_RESPONSE_EOL = """
          <response protocol=\"3.0\">
            <daystart elapsed_seconds=\"44801\"/>
            <app appid=\"%s\" status=\"ok\">
              <ping status=\"ok\"/>
              <updatecheck _eol=\"eol\" status=\"noupdate\"/>
            </app>
          </response>
        """

        def do_POST(self):
            """Handler for POST requests."""
            if self.path == '/update':

                # Parse the app id from the request to use in the response.
                content_len = int(self.headers.getheader('content-length'))
                request_string = self.rfile.read(content_len)
                request_dom = minidom.parseString(request_string)
                app = request_dom.firstChild.getElementsByTagName('app')[0]
                appid = app.getAttribute('appid')

                if self.server._devserver._eol:
                    response = self._OMAHA_RESPONSE_EOL % appid
                else:
                    (base, name) = _split_url(self.server._devserver._image_url)
                    response = self._OMAHA_RESPONSE_TEMPLATE_HEAD % appid
                    for i in range(0, self.server._devserver._num_urls):
                        response += """<url codebase=\"%s\"/>""" % (base + '/')
                    response += self._OMAHA_RESPONSE_BODY % (
                            binascii.hexlify(base64.b64decode(
                                self.server._devserver._sha256)),
                            name,
                            self.server._devserver._image_size,
                            self.server._devserver._sha256,
                            str(self.server._devserver._is_delta).lower(),
                            self.server._devserver._failures_per_url,
                            str(not self.server._devserver._backoff).lower())
                    if self.server._devserver._is_delta:
                        response += '              IsDelta="true"\n'
                    if self.server._devserver._critical:
                        response += '              deadline="now"\n'
                    if self.server._devserver._metadata_size:
                        response += '              MetadataSize="%d"\n' % (
                                self.server._devserver._metadata_size)
                    if self.server._devserver._metadata_signature:
                        response += '              ' \
                                    'MetadataSignatureRsa="%s"\n' % (
                                self.server._devserver._metadata_signature)
                    if self.server._devserver._public_key:
                        response += '              PublicKeyRsa="%s"\n' % (
                                self.server._devserver._public_key)
                    response += self._OMAHA_RESPONSE_TEMPLATE_TAIL
                self.send_response(200)
                self.send_header('Content-Type', 'application/xml')
                self.end_headers()
                self.wfile.write(response)
            else:
                self.send_response(500)

    def start(self):
        """Starts the server."""
        self._httpd = BaseHTTPServer.HTTPServer(('127.0.0.1', 0), self.Handler)
        self._httpd._devserver = self
        # Serve HTTP requests in a dedicated thread.
        thread.start_new_thread(self._httpd.serve_forever, ())
        self._port = self._httpd.socket.getsockname()[1]

    def stop(self):
        """Stops the server."""
        self._httpd.shutdown()

    def get_port(self):
        """Returns the TCP port number the server is listening on."""
        return self._port

    def get_update_url(self):
        """Returns the update url for this server."""
        return 'http://127.0.0.1:%d/update' % self._port

    def set_image_params(self, image_url, image_size, sha256,
                         metadata_size=None, metadata_signature=None,
                         public_key=None, is_delta=False, critical=True):
        """Sets the values to return in the Omaha response. Only the
        |image_url|, |image_size| and |sha256| parameters are
        mandatory."""
        self._image_url = image_url
        self._image_size = image_size
        self._sha256 = sha256
        self._metadata_size = metadata_size
        self._metadata_signature = metadata_signature
        self._public_key = public_key
        self._is_delta = is_delta
        self._critical = critical
