# Copyright 2014 The Chromium OS Authors. All rights reserved.
# Use of this source code is governed by a BSD-style license that can be
# found in the LICENSE file.

import json
import logging
import time
import urllib2

from autotest_lib.client.common_lib import error
from autotest_lib.client.common_lib import utils

URL_PING = 'ping'
URL_INFO = 'info'
URL_AUTH = 'v3/auth'
URL_PAIRING_CONFIRM = 'v3/pairing/confirm'
URL_PAIRING_START = 'v3/pairing/start'
URL_SETUP_START = 'v3/setup/start'
URL_SETUP_STATUS = 'v3/setup/status'


class PrivetdHelper(object):
    """Delegate class containing logic useful with privetd."""
    DEFAULT_HTTP_PORT = 8080
    DEFAULT_HTTPS_PORT = 8081

    def __init__(self, host=None):
        self._host = None
        self._run = utils.run
        if host is not None:
            self._host = host
            self._run = host.run
        self._http_port = self.DEFAULT_HTTP_PORT
        self._https_port = self.DEFAULT_HTTPS_PORT


    def _build_privet_url(self, path_fragment, use_https=True):
        """Builds a request URL for privet.

        @param path_fragment: URL path fragment to be appended to /privet/ URL.
        @param use_https: set to False to use 'http' protocol instead of https.

        @return The full URL to be used for request.

        """
        protocol = 'http'
        port = self._http_port
        if use_https:
            protocol = 'https'
            port = self._https_port
        hostname = '127.0.0.1'
        if self._host is not None:
            hostname = self._host.hostname
        url = '%s://%s:%s/privet/%s' % (protocol, hostname, port, path_fragment)
        return url


    def _http_request(self, url, request_data=None, retry_count=0,
                      retry_delay=0.3, headers={}):
        """Sends a GET/POST request to a web server at the given |url|.
        If the request fails due to error 111:Connection refused, try it again
        after |retry_delay| seconds and repeat this to a max |retry_count|.
        This is needed to make sure peerd has a chance to start up and start
        responding to HTTP requests.

        @param url: URL path to send the request to.
        @param request_data: json data to send in POST request.
                             If None, a GET request is sent with no data.
        @param retry_count: max request retry count.
        @param retry_delay: retry_delay (in seconds) between retries.
        @param headers: optional dictionary of http request headers
        @return The string content of the page requested at url.

        """
        logging.debug('Requesting %s', url)
        while retry_count >= 0:
            try:
                logging.info('Connecting to host: %s', url)
                request = urllib2.Request(url, request_data, headers)
                if request_data is not None:
                    request.add_header('Content-Type',
                                       'application/json; charset=utf8')
                return urllib2.urlopen(request, timeout=5).read()
            except urllib2.URLError, err:
                retry_count -= 1
                if (not str(err.reason).endswith('Connection refused') or
                        retry_count < 0):
                    raise
                logging.warn('Failed to connect to host. Retrying...')
                time.sleep(retry_delay)


    def restart_privetd(self, log_verbosity=0, enable_ping=False,
                        http_port=DEFAULT_HTTP_PORT,
                        https_port=DEFAULT_HTTPS_PORT):
        """Restart privetd in various configurations.

        @param log_verbosity: integer verbosity level of log messages.
        @param enable_ping: bool True if we should enable the ping URL
                on the privetd web server.
        @param http_port: integer port number for the privetd HTTP server.
        @param https_port: integer port number for the privetd HTTPS server.

        """
        self._http_port = http_port
        self._https_port = https_port
        flag_list = []
        flag_list.append('PRIVETD_LOG_LEVEL=%d' % log_verbosity)
        flag_list.append('PRIVETD_HTTP_PORT=%d' % self._http_port)
        flag_list.append('PRIVETD_HTTPS_PORT=%d' % self._https_port)
        if enable_ping:
            flag_list.append('PRIVETD_ENABLE_PING=true')
        self._run('stop privetd', ignore_status=True)
        self._run('start privetd %s' % ' '.join(flag_list))


    def send_privet_request(self, path_fragment, request_data=None,
                            auth_token='anonymous'):
        """Sends a privet request over HTTPS.

        @param path_fragment: URL path fragment to be appended to /privet/ URL.
        @param request_data: json data to send in POST request.
                             If None, a GET request is sent with no data.
        @param auth_token: authorization token to be added as 'Authorization'
                           http header using 'Privet' as the auth realm.

        """
        headers = {'Authorization': 'Privet %s' % auth_token}
        url = self._build_privet_url(path_fragment, True)
        data = self._http_request(url, request_data=request_data,
                                  headers=headers)
        json_data = json.loads(data)
        logging.info('Received /privet/%s response JSON: %s',
                     path_fragment, json.dumps(json_data))
        return json_data


    def ping_server(self, use_https=False):
        """Ping the privetd webserver.

        Reuses port numbers from the last restart request.  The server
        must have been restarted with enable_ping=True for this to work.

        @param use_https: set to True to use 'https' protocol instead of 'http'.

        """
        url = self._build_privet_url(URL_PING, use_https=use_https);
        content = self._http_request(url, retry_count=5)
        if content != 'Hello, world!':
            raise error.TestFail('Unexpected response from web server.')
