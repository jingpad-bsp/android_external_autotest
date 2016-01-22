# Copyright 2015 The Chromium OS Authors. All rights reserved.
# Use of this source code is governed by a BSD-style license that can be
# found in the LICENSE file.

import logging
import threading

from autotest_lib.client.common_lib import error
from autotest_lib.client.cros import enterprise_policy_base
from SocketServer import ThreadingTCPServer, StreamRequestHandler

POLICY_NAME = 'ProxySettings'
PROXY_HOST = 'localhost'
PROXY_PORT = 3128
FIXED_PROXY = '''
{
  "ProxyMode":"fixed_servers",
  "ProxyServer":"localhost:%s"
}
''' % str(PROXY_PORT)


class ProxyHandler(StreamRequestHandler):
    """Provide a request handler for the Threaded Proxy Server."""
    wbufsize = -1

    def handle(self):
        """Get URL of request from first line.

        Read the first line of the request, up to 40 characters, and look for
        the URL of the request. If found, save it to the URL list.

        Note: All requests are sent an HTTP 504 error.
        """
        # Read up to 40 characters of the request to capture the request URL
        data = self.rfile.readline(40).strip()
        logging.info('ProxyHandler::handle(): <%s>', data)
        self.server.store_requests_recieved(data)
        self.wfile.write('HTTP/1.1 504 Gateway Timeout\r\n' +
                         'Connection: close\r\n\r\n')


class ThreadedProxyServer(ThreadingTCPServer):
    """Provide a Threaded TCP Server to service and save requests.

    Define a Threaded TCP Server which services requests, and allows the
    handler to save all requests.
    """

    def __init__(self, server_address, HandlerClass):
        """Constructor.

        @param server_address: tuple of server IP and port to listen on.
        @param HandlerClass: the RequestHandler class to instantiate per req.
        """
        self._requests_recieved = []
        ThreadingTCPServer.__init__(self, server_address, HandlerClass)

    def store_requests_recieved(self, request):
        """Add receieved request to list.

        @param request: request received by the proxy server.
        """
        self._requests_recieved.append(request)

    def get_requests_recieved(self):
        """Get list of received requests."""
        return self._requests_recieved

    # TODO(krishnargv) add a method to reset request_recieved_stack


class ProxyListener(object):
    """Provide a Proxy Listener to detect connect requests.

    Defines fake listener for tracking whether an expected CONNECT request is
    seen at the provided server address. Any requests recieved are exposed to
    be consumed by the caller.
    """

    def __init__(self, server_address):
        """Constructor.

        @param server_address: tuple of server IP and port to listen on.
        """
        self._server = ThreadedProxyServer(server_address, ProxyHandler)
        self._thread = threading.Thread(target=self._server.serve_forever)

    def run(self):
        """Run the server on a thread."""
        self._thread.start()

    def stop(self):
        """Stop the server and its threads."""
        self._server.shutdown()
        self._server.socket.close()
        self._thread.join()

    def get_requests_recieved(self):
        return self._server.get_requests_recieved()


class policy_ProxySettings(enterprise_policy_base.EnterprisePolicyTest):
    """Test effect of ProxySettings policy on Chrome OS behavior."""
    version = 1
    TEST_CASES = {
        'FixedProxy': '1'
    }
    TEST_CASE_DATA = {
        'FixedProxy': FIXED_PROXY
    }

    def initialize(self, args=()):
        super(policy_ProxySettings, self).initialize(args)
        self._proxy_server = ProxyListener(('', PROXY_PORT))
        self._proxy_server.run()

    def cleanup(self):
        self._proxy_server.stop()
        super(policy_ProxySettings, self).cleanup()

    def test_fixed_proxy(self, policy_value, policies_json):
        """Verify CrOS enforces ProxySettings value = fixed-proxy.

        @param policy_value: policy value expected on chrome://policy page.
        @param policies_json: policy JSON data to send to the fake DM server.
        """
        proxy_server_requests = []
        matching_requests = []
        url = 'http://www.wired.com/'

        self.setup_case(POLICY_NAME, policy_value, policies_json)
        tab = self.cr.browser.tabs.New()
        logging.info('Navigating to URL:%s', url)
        tab.Navigate(url, timeout=10)
        proxy_server_requests = self._proxy_server.get_requests_recieved()
        matching_requests = [request for request in proxy_server_requests
                             if url in request]
        if not matching_requests:
            raise error.TestFail('Fixed Proxy Policy not applied')

    def _run_test_case(self, case):
        """Setup and run the test configured for the specified test case.

        Set the expected |policy_value| and |policies_json| data based on the
        test |case|. If the user specified an expected |value| in the command
        line args, then use it to set the |policy_value| and blank out the
        |policies_json|.

        @param case: Name of the test case to run.

        """
        policy_value = None
        policies_json = None

        if self.is_value_given:
            # If |value| was given i the command line args, then set expected
            # |policy_value| to the given value, and |policies_json| to None.
            policy_value = self.value
            policies_json = None
        else:
            # Otherwise, set expected |policy_value| and setup |policies_json|
            # data to the values required by the specified test |case|.
            if not self.TEST_CASES[case]:
                policy_value = None
            else:
                policy_value = self.TEST_CASE_DATA[case]
                policies_json = {POLICY_NAME: self.TEST_CASE_DATA[case]}

        if case == 'FixedProxy':
            self.test_fixed_proxy(policy_value, policies_json)

    def run_once(self):
        self.run_once_impl(self._run_test_case)
