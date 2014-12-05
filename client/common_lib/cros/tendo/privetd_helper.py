# Copyright 2014 The Chromium OS Authors. All rights reserved.
# Use of this source code is governed by a BSD-style license that can be
# found in the LICENSE file.

import logging
import time
import urllib2

from autotest_lib.client.common_lib import error
from autotest_lib.client.common_lib import utils


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


    def _fetch_url_with_retries(self, url, retry_count, delay):
        """Sends a GET request to a web server at the given |url|.
        If the request fails due to error 111:Connection refused, try it again
        after |delay| seconds and repeat this to a max |retry_count|.
        This is needed to make sure peerd has a chance to start up and start
        responding to HTTP requests.

        @param url: URL to send the request to.
        @param retry_count: max request retry count.
        @param delay: delay (in seconds) between retries.
        @return The string content of the page requested at |url|.

        """
        logging.debug('Requesting %s', url)
        while retry_count > 0:
            try:
                logging.info('Connecting to host: %s', url)
                return urllib2.urlopen(url, timeout=5).read()
            except urllib2.URLError, err:
                retry_count -= 1
                if (not str(err.reason).endswith('Connection refused') or
                        retry_count < 1):
                    raise
                logging.warn('Failed to connect to host. Retrying...')
                time.sleep(delay)


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


    def ping_server(self, use_https=False):
        """Ping the privetd webserver.

        Reuses port numbers from the last restart request.  The server
        must have been restarted with enable_ping=True for this to work.

        @param use_https: True if this request should be sent over HTTPS.

        """
        protocol = 'http'
        port = self._http_port
        if use_https:
            protocol = 'https'
            port = self._https_port
        hostname = '127.0.0.1'
        if self._host is not None:
            hostname = self._host.hostname
        url = '%s://%s:%s/privet/ping' % (protocol, hostname, port)
        content = self._fetch_url_with_retries(url, 5, 0.3)
        if content != 'Hello, world!':
            raise error.TestFail('Unexpected response from web server.')
