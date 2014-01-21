# Copyright (c) 2014 The Chromium OS Authors. All rights reserved.
# Use of this source code is governed by a BSD-style license that can be
# found in the LICENSE file.

import os
import re

from autotest_lib.client.bin import utils
from autotest_lib.client.cros import constants, httpd
from autotest_lib.server import autotest


class DisplayClient(object):
    """DisplayClient is a layer to control display logic over a remote DUT.

    The Autotest host object representing the remote DUT, passed to this
    class on initialization, can be accessed from its _client property.

    """

    HTTPD_PORT = 12345
    X_ENV_VARIABLES = 'DISPLAY=:0.0 XAUTHORITY=/home/chronos/.Xauthority'
    XMLRPC_CONNECT_TIMEOUT = 30


    def __init__(self, host):
        """Construct a DisplayClient.

        @param host: Host object representing a remote host.
        """
        self._client = host
        self._display_xmlrpc_client = None
        self._http_listener = None
        self._server_ip = None


    def initialize(self, test_data_dir=None):
        """Initializes some required servers, like HTTP daemon, RPC connection.

        @param test_data_dir: Path to the test data directory. A HTTP daemon
                serves this directory as its root. If None, the HTTP daemon
                doesn't run.
        """
        # Make sure the client library is on the device so that the proxy code
        # is there when we try to call it.
        client_at = autotest.Autotest(self._client)
        client_at.install()

        # Start up the XML-RPC proxy on the client.
        self._display_xmlrpc_client = self._client.xmlrpc_connect(
                constants.DISPLAY_TESTING_XMLRPC_SERVER_COMMAND,
                constants.DISPLAY_TESTING_XMLRPC_SERVER_PORT,
                command_name=(
                    constants.DISPLAY_TESTING_XMLRPC_SERVER_CLEANUP_PATTERN
                ),
                ready_test_name=(
                    constants.DISPLAY_TESTING_XMLRPC_SERVER_READY_METHOD),
                timeout_seconds=self.XMLRPC_CONNECT_TIMEOUT)

        if test_data_dir:
            # TODO(waihong): Move the test data to a centralized place.
            self._http_listener = httpd.HTTPListener(
                    port=self.HTTPD_PORT,
                    docroot=os.path.join(test_data_dir, 'calibration_images'))
            self._http_listener.run()
            # SSH_CONNECTION is of the form:
            # [client_ip] [client_port] [server_ip] [server_port]
            self._server_ip = re.search(
                    r'([0-9.]+) \d+ [0-9.]+ \d+',
                    self._client.run('echo $SSH_CONNECTION').stdout).group(1)


    def cleanup(self):
        """Cleans up."""
        if self._http_listener:
            self._http_listener.stop()
        self._client.rpc_disconnect_all()


    def __del__(self):
        """Destructor of DisplayClient."""
        self.cleanup()


    def get_connector_name(self):
        """Gets the name of the external output connector.

        @return The external output connector name as a string.
        """
        return self._display_xmlrpc_client.get_ext_connector_name()


    def load_calibration_image(self, resolution):
        """Load a full screen calibration image from the HTTP server.

        @param resolution: A tuple (width, height) of resolution.
        """
        resolution_str = '%dx%d' % resolution
        page_url = ('http://%s:%s/%s.png' %
                    (self._server_ip, self.HTTPD_PORT, resolution_str))
        self._display_xmlrpc_client.load_url(page_url)


    def close_tab(self, index=-1):
        """Closes the tab of the given index.

        @param index: The tab index to close. Defaults to the last tab.
        """
        return self._display_xmlrpc_client.close_tab(index)


    def set_mirrored(self, is_mirrored):
        """Sets mirrored mode.

        @param is_mirrored: True or False to indicate mirrored state.
        """
        return self._display_xmlrpc_client.set_mirrored(is_mirrored)


    def suspend_resume(self):
        """Suspends the DUT for 10 seconds."""
        # TODO(waihong): Use other general API instead of this RPC.
        return self._display_xmlrpc_client.suspend_resume()


    def reconnect_output_and_wait(self):
        """Reconnects output and waits it available."""
        output = self.get_connector_name()
        self._display_xmlrpc_client.reconnect_output(output)
        self._display_xmlrpc_client.wait_output_connected(output)
        utils.wait_for_value(lambda: (
                len(self._display_xmlrpc_client.get_display_info())),
                expected_value=2)


    def move_cursor_to_bottom_right(self):
        """Moves mouse cursor to the bottom-right corner."""
        output = self.get_connector_name()
        fb_w, fb_h, _, _ = self._display_xmlrpc_client.get_resolution(output)
        self._client.run('%s xdotool mousemove %d %d' %
                       (self.X_ENV_VARIABLES, fb_w, fb_h))


    def capture_external_screen(self, file_path):
        """Captures the external screen framebuffer.

        @param file_path: The path of file for output.

        @return: The byte-array for the screen.
        """
        output = self.get_connector_name()
        fb_w, fb_h, fb_x, fb_y = (
                self._display_xmlrpc_client.get_resolution(output))
        basename = os.path.basename(file_path)
        remote_path = os.path.join('/tmp', basename)
        command = ('%s import -window root -depth 8 -crop %dx%d+%d+%d %s' %
                   (self.X_ENV_VARIABLES, fb_w, fb_h, fb_x, fb_y, remote_path))
        self._client.run(command)
        self._client.get_file(remote_path, file_path)
        return open(file_path).read()
