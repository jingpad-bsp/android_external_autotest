# Copyright (c) 2011 The Chromium OS Authors. All rights reserved.
# Use of this source code is governed by a BSD-style license that can be
# found in the LICENSE file.

import subprocess

from autotest_lib.client.common_lib import error
from autotest_lib.server import test
import autotest_lib.server.cros.servo

class ServoTest(test.test):
    """AutoTest test class that creates and destroys a servo object.

    Servo-based server side AutoTests can inherit from this object.
    """
    version = 1
    servo = None
    _ip = None


    def initialize(self, host, servo_port, xml_config='servo.xml',
                   servo_vid=None, servo_pid=None, servo_serial=None):
        """Create a Servo object."""
        self.servo = autotest_lib.server.cros.servo.Servo(
                servo_port, xml_config, servo_vid, servo_pid, servo_serial)

        # Initializes dut, may raise AssertionError if pre-defined gpio
        # sequence to set GPIO's fail.  Autotest does not handle exception
        # throwing in initialize and will cause a test to hang.
        try:
            self.servo.initialize_dut()
        except AssertionError as e:
            del self.servo
            raise error.TestFail(e)

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
        if self.servo: del self.servo
