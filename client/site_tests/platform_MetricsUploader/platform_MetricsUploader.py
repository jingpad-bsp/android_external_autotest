# Copyright 2014 The Chromium OS Authors. All rights reserved.
# Use of this source code is governed by a BSD-style license that can be
# found in the LICENSE file.

import SimpleHTTPServer
import threading

from autotest_lib.client.bin import test
from autotest_lib.client.common_lib import error, utils
from autotest_lib.client.cros import httpd, service_stopper


class FakeServer(SimpleHTTPServer.SimpleHTTPRequestHandler):
    """
    Fake Uma server. Does not check the actual protobuf format.
    """


    messages_count = 0


    def do_POST(self):
        """
        Answer 'OK' with a 200 HTTP status code on POST requests to /uma/v2
        and an empty message with error code 404 otherwise.
        """
        if self.path != "/uma/v2":
            self.send_response(404)
            self.end_headers()
            return

        self.send_response(200)
        self.send_header('Content-type', 'text/html')
        self.end_headers()
        self.wfile.write('OK')
        FakeServer.messages_count += 1


    def messages_count(self):
        """
        Returns the number of valid request received.
        """
        return self._messages_count


    def run(self):
        """
        Start the server
        """
        self._server.run()


class platform_MetricsUploader(test.test):
    """
    Test that metrics_daemon is sending the metrics to the Uma server when
    started with the -uploader flag.
    """
    version = 1


    def initialize(self):
        self._services = service_stopper.ServiceStopper(['metrics_daemon'])
        self._services.stop_services()


    def run_once(self):
        """
        Run the test.
        """
        utils.system_output('truncate --size=0 /var/run/metrics/uma-events')
        utils.system_output('metrics_client test 10 0 100 10')

        server = httpd.ThreadedHTTPServer(('', 8080), FakeServer)
        server_thread = threading.Thread(target=server.serve_forever)
        server_thread.start()

        utils.system_output('metrics_daemon -uploader_test '
                            '-server="http://localhost:8080/uma/v2"',
                            timeout=10, retain_output=True)

        if FakeServer.messages_count == 0:
            raise error.TestFail('no messages received by the server')


    def cleanup(self):
        self._services.restore_services()
