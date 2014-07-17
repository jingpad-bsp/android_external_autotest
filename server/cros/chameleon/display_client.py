# Copyright (c) 2014 The Chromium OS Authors. All rights reserved.
# Use of this source code is governed by a BSD-style license that can be
# found in the LICENSE file.

import Image
import httplib
import logging
import os
import socket
import tempfile
import xmlrpclib

from autotest_lib.client.bin import utils
from autotest_lib.client.common_lib.cros import retry
from autotest_lib.client.cros import constants
from autotest_lib.server import autotest
from autotest_lib.server.cros.chameleon import image_generator


class DisplayClient(object):
    """DisplayClient is a layer to control display logic over a remote DUT.

    The Autotest host object representing the remote DUT, passed to this
    class on initialization, can be accessed from its _client property.

    """

    X_ENV_VARIABLES = 'DISPLAY=:0.0 XAUTHORITY=/home/chronos/.Xauthority'
    XMLRPC_CONNECT_TIMEOUT = 30
    XMLRPC_RETRY_TIMEOUT = 180
    XMLRPC_RETRY_DELAY = 10
    HTTP_PORT = 8000
    DEST_TMP_DIR = '/tmp'
    DEST_IMAGE_FILENAME = 'calibration.svg'


    def __init__(self, host):
        """Construct a DisplayClient.

        @param host: Host object representing a remote host.
        """
        self._client = host
        self._display_xmlrpc_client = None
        self._image_generator = image_generator.ImageGenerator()


    def initialize(self):
        """Initializes some required servers, like HTTP daemon, RPC connection.
        """
        # Make sure the client library is on the device so that the proxy code
        # is there when we try to call it.
        client_at = autotest.Autotest(self._client)
        client_at.install()
        self.connect()


    def connect(self):
        """Connects the XML-RPC proxy on the client."""
        @retry.retry((socket.error,
                      xmlrpclib.ProtocolError,
                      httplib.BadStatusLine),
                     timeout_min=self.XMLRPC_RETRY_TIMEOUT / 60.0,
                     delay_sec=self.XMLRPC_RETRY_DELAY)
        def connect_with_retries():
            """Connects the XML-RPC proxy with retries."""
            self._display_xmlrpc_client = self._client.xmlrpc_connect(
                    constants.DISPLAY_TESTING_XMLRPC_SERVER_COMMAND,
                    constants.DISPLAY_TESTING_XMLRPC_SERVER_PORT,
                    command_name=(
                        constants.DISPLAY_TESTING_XMLRPC_SERVER_CLEANUP_PATTERN
                    ),
                    ready_test_name=(
                        constants.DISPLAY_TESTING_XMLRPC_SERVER_READY_METHOD),
                    timeout_seconds=self.XMLRPC_CONNECT_TIMEOUT)

        logging.info('Setup the display_client RPC server, with retries...')
        connect_with_retries()


    def cleanup(self):
        """Cleans up."""
        self._client.rpc_disconnect(
                constants.DISPLAY_TESTING_XMLRPC_SERVER_PORT)


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
        with tempfile.NamedTemporaryFile() as f:
            self._image_generator.generate_image(
                    resolution[0], resolution[1], f.name)
            os.chmod(f.name, 0644)
            self._client.send_file(
                    f.name,
                    os.path.join(self.DEST_TMP_DIR, self.DEST_IMAGE_FILENAME))

        page_url = 'file://%s/%s' % (self.DEST_TMP_DIR,
                                     self.DEST_IMAGE_FILENAME)
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


    def suspend_resume(self, suspend_time=10):
        """Suspends the DUT for a given time in second.

        @param suspend_time: Suspend time in second, default: 10s.
        """
        # TODO(waihong): Use other general API instead of this RPC.
        return self._display_xmlrpc_client.suspend_resume(suspend_time)


    def suspend_resume_bg(self, suspend_time=10):
        """Suspends the DUT for a given time in second in the background.

        @param suspend_time: Suspend time in second, default: 10s.
        """
        # TODO(waihong): Use other general API instead of this RPC.
        return self._display_xmlrpc_client.suspend_resume_bg(suspend_time)


    def reconnect_output_and_wait(self):
        """Reconnects output and waits it available."""
        output = self.get_connector_name()
        self._display_xmlrpc_client.reconnect_output(output)
        self._display_xmlrpc_client.wait_output_connected(output)
        utils.wait_for_value(lambda: (
                len(self._display_xmlrpc_client.get_display_info())),
                expected_value=2)


    def hide_cursor(self):
        """Hides mouse cursor by sending a keystroke."""
        self._display_xmlrpc_client.press_key('Up')


    def capture_external_screen(self):
        """Captures the external screen framebuffer.

        @return: An Image object.
        """
        output = self.get_connector_name()
        fb_w, fb_h, fb_x, fb_y = (
                self._display_xmlrpc_client.get_resolution(output))
        with tempfile.NamedTemporaryFile(suffix='.png') as f:
            basename = os.path.basename(f.name)
            remote_path = os.path.join('/tmp', basename)
            command = ('%s import -window root -depth 8 -crop %dx%d+%d+%d %s' %
                       (self.X_ENV_VARIABLES, fb_w, fb_h, fb_x, fb_y,
                        remote_path))
            self._client.run(command)
            self._client.get_file(remote_path, f.name)
            return Image.open(f.name)


    def get_resolution(self):
        """Gets the external resolution on framebuffer.

        @return The resolution tuple (width, height)
        """
        output = self.get_connector_name()
        width, height, _, _ = self._display_xmlrpc_client.get_resolution(output)
        return (width, height)
