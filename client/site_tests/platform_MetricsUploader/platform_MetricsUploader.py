# Copyright 2014 The Chromium OS Authors. All rights reserved.
# Use of this source code is governed by a BSD-style license that can be
# found in the LICENSE file.

import logging
import os
import SimpleHTTPServer
import sys
import threading

from autotest_lib.client.bin import test
from autotest_lib.client.common_lib import autotemp, error, file_utils, utils
from autotest_lib.client.cros import httpd, service_stopper


class FakeHandler(SimpleHTTPServer.SimpleHTTPRequestHandler):
    """
    Fake Uma handler.

    Answer OK on well formed request and add the data to the server's list of
    messages.
    """

    def do_POST(self):
        """
        Handle post request to the fake UMA backend.

        Answer 'OK' with a 200 HTTP status code on POST requests to /uma/v2
        and an empty message with error code 404 otherwise.
        """
        if self.path != '/uma/v2':
            self.send_response(404)
            self.end_headers()
            return

        message = self.rfile.read(int(self.headers['Content-Length']))
        self.server.messages.append(message)

        self.send_response(200)
        self.send_header('Content-type', 'text/html')
        self.end_headers()
        self.wfile.write('OK')


class FakeServer(httpd.ThreadedHTTPServer):
    """
    Wrapper around ThreadedHTTPServer.

    Provides helpers to start/stop the instance and hold the list of
    received messages.
    """

    def __init__(self):
        httpd.ThreadedHTTPServer.__init__(self, ('', 8080), FakeHandler)
        self.messages = []


    def Start(self):
        """
        Start the server on a new thread.
        """
        self.server_thread = threading.Thread(target=self.serve_forever)
        self.server_thread.start()


    def Stop(self):
        """
        Stop the server thread.
        """
        self.shutdown()
        self.socket.close()
        self.server_thread.join()


class platform_MetricsUploader(test.test):
    """
    End-to-End test of the metrics uploader

    Test that metrics_daemon is sending the metrics to the Uma server when
    started with the -uploader flag and that the messages are well formatted.
    """

    version = 1

    def setup(self):
        os.chdir(self.srcdir)
        utils.make('OUT_DIR=.')


    def initialize(self):
        self._services = service_stopper.ServiceStopper(['metrics_daemon'])
        self._services.stop_services()
        self._tempdir = autotemp.tempdir()


    def _create_one_sample(self):
        utils.system_output('truncate --size=0 /var/run/metrics/uma-events')
        utils.system_output('metrics_client test 10 0 100 10')


    def _test_simple_upload(self):
        self._create_one_sample()

        self.server = FakeServer()
        self.server.Start()

        utils.system_output('metrics_daemon -uploader_test '
                            '-server="http://localhost:8080/uma/v2"',
                            timeout=10, retain_output=True)

        self.server.Stop()

        if len(self.server.messages) != 1:
            raise error.TestFail('no messages received by the server')


    def _test_server_unavailable(self):
        """
        metrics_daemon should not crash when the server is unavailable.
        """
        self._create_one_sample()
        utils.system_output('metrics_daemon -uploader_test '
                            '-server="http://localhost:12345"',
                            retain_output=True)


    def _test_check_product_id(self):
        """
        metrics_daemon should set the product id when it is specified.

        The product id can be set through the GOOGLE_METRICS_PRODUCT_ID file in
        /etc/os-release.d/.
        """

        # The product id must be an integer, declared in the upstream UMA
        # backend protobuf.
        EXPECTED_PRODUCT_ID = 3

        sys.path.append(self.srcdir)
        from chrome_user_metrics_extension_pb2 import ChromeUserMetricsExtension

        self._create_one_sample()

        self.server = FakeServer()
        self.server.Start()
        osreleased_path = os.path.join(self._tempdir.name, 'etc',
                                       'os-release.d')
        file_utils.make_leaf_dir(osreleased_path)
        utils.write_one_line(os.path.join(osreleased_path,
                                          'GOOGLE_METRICS_PRODUCT_ID'),
                             str(EXPECTED_PRODUCT_ID))

        utils.system_output('metrics_daemon -uploader_test '
                            '-server="http://localhost:8080/uma/v2" '
                            '-config_root="%s"' % self._tempdir.name,
                            retain_output=True)

        self.server.Stop()

        if len(self.server.messages) != 1:
            raise error.TestFail('should have received 1 message. Received: '
                               + str(len(self.server.messages)))

        proto = ChromeUserMetricsExtension.FromString(self.server.messages[0])
        logging.debug('Proto received is: ' + str(proto))
        if proto.product != EXPECTED_PRODUCT_ID:
            raise error.TestFail('Product id should be set to 3. Was: '
                                 + str(proto.product))


    def run_once(self):
        """
        Run the tests.
        """
        logging.info(('=' * 4) + 'Check that metrics samples can be uploaded '
                     'with the default configuration')
        self._test_simple_upload()

        logging.info(('=' * 4) + 'Check that the metrics uploader does not '
                     'crash when the backend server is unreachable')
        self._test_server_unavailable()

        logging.info(('=' * 4) + 'Check that the product id can be set '
                     'through the GOOGLE_METRICS_PRODUCT_ID field in '
                     '/etc/os-release.d/')
        self._test_check_product_id()


    def cleanup(self):
        self._services.restore_services()
        self._tempdir.clean()
