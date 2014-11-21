# Copyright 2014 The Chromium OS Authors. All rights reserved.
# Use of this source code is governed by a BSD-style license that can be
# found in the LICENSE file.

import logging
import time
import urllib2

from autotest_lib.server import test
from autotest_lib.client.common_lib import error

class privetd_WebServerSanity(test.test):
    """Test that we can connect to privetd's web server and get a response
    from a simple GET request."""
    version = 1
    HTTP_PORT = 8080
    HTTPS_PORT = 8081

    def fetch_url_with_retries(self, url, retry_count, delay):
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

    def ping_server(self, proto, hostname, port):
        """Tests an instance of a web server on particular port.

        @param proto: protocol to use (http/https).
        @param hostname: host name/IP address.
        @param port: TCP port to use.
        """
        url = '%s://%s:%s/privet/ping' % (proto, hostname, port)
        content = self.fetch_url_with_retries(url, 5, 0.1)
        if content != 'Hello, world!':
            raise error.TestFail('Unexpected response from web server.')

    def warmup(self, host):
        host.run('stop privetd', ignore_status=True)
        host.run('start privetd PRIVETD_LOG_LEVEL=3 '
                 'PRIVETD_HTTP_PORT=%s PRIVETD_HTTPS_PORT=%s '
                 'PRIVETD_ENABLE_PING=true' % (self.HTTP_PORT, self.HTTPS_PORT))

    def cleanup(self, host):
        host.run('stop privetd')
        host.run('start privetd')

    def run_once(self, host):
        self.ping_server("http", host.hostname, self.HTTP_PORT)
        self.ping_server("https", host.hostname, self.HTTPS_PORT)
