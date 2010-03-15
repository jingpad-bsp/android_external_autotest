#!/usr/bin/python

# Copyright (c) 2010 The Chromium OS Authors. All rights reserved.
# Use of this source code is governed by a BSD-style license that can be
# found in the LICENSE file.

"""Spins up a trivial HTTP cgi form listener in a thread.

   This HTTPThread class is a utility for use with test cases that
   need to call back to the Autotest test case with some form value, e.g.
   http://localhost:nnnn/?status="Browser started!"
"""

import cgi, logging, os, posixpath, SimpleHTTPServer, sys, threading
import urllib, urlparse
from BaseHTTPServer import BaseHTTPRequestHandler, HTTPServer


class FormHandler(SimpleHTTPServer.SimpleHTTPRequestHandler):
    """Implements a form handler (for POST requests only) which simply
    echoes the key=value parameters back in the response.

    If the form submission is a file upload, the file will be written
    to disk with the name contained in the 'filename' field.
    """
    def do_POST(self):
        form = cgi.FieldStorage(
            fp=self.rfile,
            headers=self.headers,
            environ={'REQUEST_METHOD': 'POST',
                     'CONTENT_TYPE': self.headers['Content-Type']})
        for field in form.keys():
            field_item = form[field]
            self.server._form_entries[field] = field_item.value
        path = urlparse.urlparse(self.path)[2]
        if path in self.server._url_handlers:
            self.server._url_handlers[path](self, form)
        else:
            # Echo back information about what was posted in the form.
            self.write_post_response(form)
        self._fire_event()


    def write_post_response(self, form):
        """Called to fill out the response to an HTTP POST.

        Override this class to give custom responses.
        """
        # Send response boilerplate
        self.send_response(200)
        self.end_headers()
        self.wfile.write('Hello from Autotest!\nClient: %s\n' %
                         str(self.client_address))
        self.wfile.write('Request for path: %s\n' % self.path)
        self.wfile.write('Got form data:\n')

        for field in form.keys():
            field_item = form[field]
            if field_item.filename:
                # The field contains an uploaded file
                upload = field_item.file.read()
                self.wfile.write('\tUploaded %s (%d bytes)<br>' %
                                 (field, len(upload)))
                # Write submitted file to specified filename.
                file(field_item.filename, 'w').write(upload)
                del upload
            else:
                self.wfile.write('\t%s=%s<br>' % (field, form[field].value))


    def translate_path(self, path):
        """Override SimpleHTTPRequestHandler's translate_path to serve
        from arbitrary docroot
        """
        # abandon query parameters
        path = urlparse.urlparse(path)[2]
        path = posixpath.normpath(urllib.unquote(path))
        words = path.split('/')
        words = filter(None, words)
        path = self.server.docroot
        for word in words:
            drive, word = os.path.splitdrive(word)
            head, word = os.path.split(word)
            if word in (os.curdir, os.pardir): continue
            path = os.path.join(path, word)
        return path


    def _fire_event(self):
        wait_urls = self.server._wait_urls
        if self.path in wait_urls:
            _, e = wait_urls[self.path]
            e.set()
            del wait_urls[self.path]
        else:
            logging.debug('URL %s not in watch list' % self.path)


    def do_GET(self):
        form = cgi.FieldStorage(
            fp=self.rfile,
            headers=self.headers,
            environ={'REQUEST_METHOD': 'GET'})
        split_url = urlparse.urlsplit(self.path)
        path = split_url[2]
        args = urlparse.parse_qs(split_url[3])
        if path in self.server._url_handlers:
            self.server._url_handlers[path](self, args)
        else:
            SimpleHTTPServer.SimpleHTTPRequestHandler.do_GET(self)
        self._fire_event()


class HTTPListener(object):
    def __init__(self, port=0, docroot=None, wait_urls={}, url_handlers={}):
        self._server = HTTPServer(('', port), FormHandler)
        # Stuff some convenient data fields into the server object.
        self._server.docroot = docroot
        self._server._wait_urls = wait_urls
        self._server._url_handlers = url_handlers
        self._server._form_entries = {}
        self._server_thread = threading.Thread(
            target=self._server.serve_forever)


    def add_wait_url(self, url='/', matchParams={}):
        e = threading.Event()
        self._server._wait_urls[url] = (matchParams, e)
        return e


    def add_url_handler(self, url, handler_func):
        self._server._url_handlers[url] = handler_func


    def clear_form_entries(self):
        self._server._form_entries = {}


    def get_form_entries(self):
        """Returns a dictionary of all field=values recieved by the server.
        """
        return self._server._form_entries


    def run(self):
        logging.debug('http server on %s:%d' %
                      (self._server.server_name, self._server.server_port))
        self._server_thread.start()


    def stop(self):
        self._server.shutdown()
