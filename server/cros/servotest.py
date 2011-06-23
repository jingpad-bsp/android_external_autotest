# Copyright (c) 2011 The Chromium OS Authors. All rights reserved.
# Use of this source code is governed by a BSD-style license that can be
# found in the LICENSE file.

import subprocess

from autotest_lib.server import test, autotest
import autotest_lib.server.cros.servo

class ServoTest(test.test):
    """AutoTest test class that creates and destroys a servo object.

    Servo-based server side AutoTests can inherit from this object.
    """
    version = 1
    servo = None
    _ip = None


    def initialize(self, host, servo_port, xml_config='servo.xml'):
        """Create a Servo object."""
        self.servo = autotest_lib.server.cros.servo.Servo(servo_port,
                                                          xml_config)
        self._ip = host.ip


    def assert_ping(self):
        """Ping to assert that the device is up."""
        assert self.ping_test(self._ip)


    def assert_pingfail(self):
        """Ping to assert that the device is down."""
        assert not self.ping_test(self._ip)


    def ping_test(self, hostname, timeout=5):
        """Verify whether a host responds to a ping.

        Args:
          hostname: Hostname to ping.
          timeout: Time in seconds to wait for a response.
        """
        return subprocess.call(['ping', '-c', '1', '-W',
                                str(timeout), hostname]) == 0


    def cleanup(self):
        """Delete the Servo object."""
        del self.servo
