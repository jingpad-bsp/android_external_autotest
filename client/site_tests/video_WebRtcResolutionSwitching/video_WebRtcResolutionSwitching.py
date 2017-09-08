# Copyright 2017 The Chromium OS Authors. All rights reserved.
# Use of this source code is governed by a BSD-style license that can be
# found in the LICENSE file.

from autotest_lib.client.bin import test
from autotest_lib.client.common_lib.cros import test_webrtc_peer_connection

EXTRA_BROWSER_ARGS = ['--use-fake-ui-for-media-stream',
                      '--use-fake-device-for-media-stream']

class video_WebRtcResolutionSwitching(test.test):
    """Tests multiple peerconnections that randomly change resolution."""
    version = 1

    def run_once(self):
        """Runs the test."""
        test = test_webrtc_peer_connection.WebRtcPeerConnectionTest(
            title = 'Resolution Switching',
            own_script = 'resolution-switching.js',
            common_script = 'loopback-peerconnection.js',
            bindir = self.bindir,
            tmpdir = self.tmpdir,
            num_peer_connections = 5,
            iteration_delay_millis = 300)
        test.run_test()

