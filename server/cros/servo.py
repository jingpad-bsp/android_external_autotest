# Copyright (c) 2011 The Chromium OS Authors. All rights reserved.
# Use of this source code is governed by a BSD-style license that can be
# found in the LICENSE file.
#
# Expects to be run in an environment with sudo and no interactive password
# prompt, such as within the Chromium OS development chroot.


import time
import xmlrpclib
import subprocess


class Servo:
    """Manages control of a Servo board.

    Servo is a board developed by hardware group to aide in the debug and
    control of various partner devices. Servo's features include the simulation
    of pressing the power button, closing the lid, and pressing Ctrl-d. This
    class manages setting up and communicating with a servo demon (servod)
    process. It provides both high-level functions for common servo tasks and
    low-level functions for directly setting and reading gpios.
    """

    _server = None
    _servod = None


    def __init__(self, servo_port, xml_config='servo.xml', cold_reset=False):
        """Sets up the servo communication infrastructure.

        Args:
          servo_port: Port the servod process should listen on.
          xml_config: Configuration XML file for servod.
          cold_reset: If True, cold reset device and boot during init,
                      otherwise perform init with device running.
        """
        # launch servod
        self._launch_servod(servo_port, xml_config)

        # connect to servod
        assert servo_port

        self._connect_servod(servo_port)
        if cold_reset:
            self._init_seq_cold_reset_devmode()
        else:
            self._init_seq()



    def power_long_press(self):
        """Simulate a long (8 sec) power button press."""
        self.power_key(8)


    def power_normal_press(self):
        """Simulate a normal (1 sec) power button press."""
        self.power_key(1)


    def power_short_press(self):
        """Simulate a short (0.1 sec) power button press."""
        self.power_key(0.1)


    def power_key(self, secs=1):
        """Simulate a power button press.

        Args:
          secs: Time in seconds to simulate the keypress.
        """
        self.set('pwr_button', 'press')
        time.sleep(secs)
        self.set('pwr_button', 'release')


    def lid_open(self):
        """Simulate opening the lid."""
        self.set('lid_open', 'yes')


    def lid_close(self):
        """Simulate closing the lid."""
        self.set('lid_open', 'no')


    def ctrl_d(self, secs=0.5):
        """Simulate Ctrl-d simultaneous button presses.

        Args:
          secs: Time in seconds to simulate the keypress.
        """
        self.set_nocheck('kbd_en', 'on')
        self.set_nocheck('kbd_m1', 'r2_c2')
        self.set_nocheck('kbd_m2', 'r1_c1')
        time.sleep(secs)
        self.set_nocheck('kbd_en', 'off')


    def enter_key(self, secs=0.5):
        """Simulate Enter key button press.

        Args:
          secs: Time in seconds to simulate the keypress.
        """
        self.set_nocheck('kbd_en', 'on')
        self.set_nocheck('kbd_m1', 'r3_c2')
        time.sleep(secs)
        self.set_nocheck('kbd_en', 'off')


    def refresh_key(self, secs=0.5):
        """Simulate Refresh key (F3) button press.

        Args:
          secs: Time in seconds to simulate the keypress.
        """
        self.set_nocheck('kbd_en', 'on')
        self.set_nocheck('kbd_m2', 'r2_c1')
        time.sleep(secs)
        self.set_nocheck('kbd_en', 'off')


    def imaginary_key(self, secs=0.5):
        """Simulate imaginary key button press.

        Maps to a key that doesn't physically exist.

        Args:
          secs: Time in seconds to simulate the keypress.
        """
        self.set_nocheck('kbd_en', 'on')
        self.set_nocheck('kbd_m2', 'r3_c1')
        time.sleep(secs)
        self.set_nocheck('kbd_en', 'off')


    def boot_devmode(self):
        """Boot a dev-mode device that is powered off."""
        self.set('pwr_button', 'release')
        time.sleep(1)
        self.power_normal_press()
        time.sleep(8)
        self.ctrl_d()
        time.sleep(15)

    def _init_seq_cold_reset_devmode(self):
        """Cold reset, init device, and boot in dev-mode."""
        self._cold_reset()
        self._init_seq()
        self.set('dev_mode', 'on')
        self.boot_devmode()


    def get(self, gpio_name):
        """Get the value of a gpio from Servod."""
        assert gpio_name
        return self._server.get(gpio_name)


    def set(self, gpio_name, gpio_value):
        """Set and check the value of a gpio using Servod."""
        assert gpio_name and gpio_value
        self._server.set(gpio_name, gpio_value)
        assert gpio_value == self.get(gpio_name)


    def set_nocheck(self, gpio_name, gpio_value):
        """Set the value of a gpio using Servod."""
        assert gpio_name and gpio_value
        self._server.set(gpio_name, gpio_value)


    def __del__(self):
        """Kill the Servod process."""
        assert self._servod
        # kill servod one way or another
        try:
            # won't work without superuser privileges
            self._servod.terminate()
        except:
            # should work without superuser privileges
            assert subprocess.call(['sudo', 'kill', str(self._servod.pid)])


    def _launch_servod(self, servo_port, xml_config='servo.xml'):
        """Launch the servod process.

        Args:
          servo_port: Port to start servod listening on.
          xml_config: XML configuration file for servod.
        """
        self._servod = subprocess.Popen(['sudo', 'servod', '-c',
                                         str(xml_config),
                                         '--host=localhost',
                                         '--port=' + str(servo_port)],
                                        0, None, None, None, subprocess.PIPE)
        # wait for servod to initialize
        timeout = 10
        while ("Listening" not in self._servod.stderr.readline() and
               self._servod.returncode is None and timeout > 0):
            time.sleep(1)
            timeout -= 1
        assert self._servod.returncode is None and timeout


    def _init_seq(self):
        """Initiate starting state for servo."""
        self.set('tx_dir', 'input')
        self.set('servo_dut_tx', 'off')
        self.set('lid_open', 'yes')
        self.set('rec_mode', 'off')


    def _cold_reset(self):
        """Perform a cold reset of the EC.

        Has the side effect of shutting off the device.
        """
        self.set('cold_reset', 'on')
        time.sleep(2)
        self.set('cold_reset', 'off')


    def _connect_servod(self, servo_port=''):
        """Connect to the Servod process with XMLRPC.

        Args:
          servo_port: Port the Servod process is listening on.
        """
        remote = 'http://localhost:%s' % servo_port
        self._server = xmlrpclib.ServerProxy(remote)
