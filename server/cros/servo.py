# Copyright (c) 2012 The Chromium OS Authors. All rights reserved.
# Use of this source code is governed by a BSD-style license that can be
# found in the LICENSE file.
#
# Expects to be run in an environment with sudo and no interactive password
# prompt, such as within the Chromium OS development chroot.

import logging, os, re, select, subprocess, sys, time, xmlrpclib
from autotest_lib.client.bin import utils as client_utils
from autotest_lib.client.common_lib import error
from autotest_lib.server import utils

class Servo(object):
    """Manages control of a Servo board.

    Servo is a board developed by hardware group to aide in the debug and
    control of various partner devices. Servo's features include the simulation
    of pressing the power button, closing the lid, and pressing Ctrl-d. This
    class manages setting up and communicating with a servo demon (servod)
    process. It provides both high-level functions for common servo tasks and
    low-level functions for directly setting and reading gpios.
    """

    # Power button press delays in seconds.
    #
    # The EC specification says that 8.0 seconds should be enough
    # for the long power press.  However, some platforms need a bit
    # more time.  Empirical testing has found these requirements:
    #   Alex: 8.2 seconds
    #   ZGB:  8.5 seconds
    # The actual value is set to the largest known necessary value.
    #
    # TODO(jrbarnette) Being generous is the right thing to do for
    # existing platforms, but if this code is to be used for
    # qualification of new hardware, we should be less generous.
    LONG_DELAY = 8.5
    SHORT_DELAY = 0.1
    NORMAL_TRANSITION_DELAY = 1.2

    # Maximum number of times to re-read power button on release.
    RELEASE_RETRY_MAX = 5
    GET_RETRY_MAX = 10

    # Delays to deal with DUT state transitions.
    SLEEP_DELAY = 6
    BOOT_DELAY = 10
    RECOVERY_BOOT_DELAY = 10
    RECOVERY_INSTALL_DELAY = 540

    # Time required for the EC to be working after cold reset.
    # Five seconds is at least twice as big as necessary for Alex,
    # and is presumably good enough for all future systems.
    _EC_RESET_DELAY = 5.0

    # Servo-specific delays.
    MAX_SERVO_STARTUP_DELAY = 10
    SERVO_SEND_SIGNAL_DELAY = 0.5
    SERVO_KEY_PRESS_DELAY = 0.1

    # Time between an usb disk plugged-in and detected in the system.
    USB_DETECTION_DELAY = 10

    KEY_MATRIX = {
        'm1': {'ctrl_r': ['0', '0'], 'd': ['0', '1'],
               'enter': ['1', '0'], 'none': ['1', '1']},
        'm2': {'ctrl': ['0', '0'], 'refresh': ['0', '1'],
               'unused': ['1', '0'], 'none': ['1', '1']}
        }


    @staticmethod
    def _make_servo_hostname(hostname):
        host_parts = hostname.split('.')
        host_parts[0] = host_parts[0] + '-servo'
        return '.'.join(host_parts)

    @staticmethod
    def get_lab_servo(target_hostname):
        """Instantiate a Servo for |target_hostname| in the lab.

        Assuming that |target_hostname| is a device in the CrOS test
        lab, create and return a Servo object pointed at the servo
        attached to that DUT.  The servo in the test lab is assumed
        to already have servod up and running on it.

        @param target_hostname: device whose servo we want to target.
        @return an appropriately configured Servo
        """
        servo_host = Servo._make_servo_hostname(target_hostname)
        if utils.host_is_in_lab_zone(servo_host):
          try:
              return Servo(servo_host=servo_host)
          except:
              # TODO(jrbarnette):  Long-term, if we can't get to
              # a servo in the lab, we want to fail, so we should
              # pass any exceptions along.  Short-term, we're not
              # ready to rely on servo, so we ignore failures.
              pass
        return None


    def __init__(self, servo_host='localhost', servo_port=9999):
        """Sets up the servo communication infrastructure.

        @param servo_host Name of the host where the servod process
                          is running.
        @param servo_port Port the servod process is listening on.
        """
        self._server = None
        self._connect_servod(servo_host, servo_port)


    def initialize_dut(self, cold_reset=False):
        """Initializes a dut for testing purposes.

        This sets various servo signals back to default values
        appropriate for the target board.  By default, if the DUT
        is already on, it stays on.  If the DUT is powered off
        before initialization, its state afterward is unspecified.

        If cold reset is requested, the DUT is guaranteed to be off
        at the end of initialization, regardless of its initial
        state.

        Rationale:  Basic initialization of servo sets the lid open,
        when there is a lid.  This operation won't affect powered on
        units; however, setting the lid open may power on a unit
        that's off, depending on factors outside the scope of this
        function.

        @param cold_reset If True, cold reset the device after
                          initialization.
        """
        self._server.hwinit()
        if cold_reset:
            self.cold_reset()


    def power_long_press(self):
        """Simulate a long power button press."""
        # After a long power press, the EC may ignore the next power
        # button press (at least on Alex).  To guarantee that this
        # won't happen, we need to allow the EC one second to
        # collect itself.
        self.power_key(Servo.LONG_DELAY)
        time.sleep(1.0)


    def power_normal_press(self):
        """Simulate a normal power button press."""
        self.power_key()


    def power_short_press(self):
        """Simulate a short power button press."""
        self.power_key(Servo.SHORT_DELAY)


    def power_key(self, secs=NORMAL_TRANSITION_DELAY):
        """Simulate a power button press.

        Args:
          secs: Time in seconds to simulate the keypress.
        """
        self.set_nocheck('pwr_button', 'press')
        time.sleep(secs)
        self.set_nocheck('pwr_button', 'release')
        # TODO(tbroch) Different systems have different release times on the
        # power button that this loop addresses.  Longer term we may want to
        # make this delay platform specific.
        retry = 1
        while True:
            value = self.get('pwr_button')
            if value == 'release' or retry > Servo.RELEASE_RETRY_MAX:
                break
            logging.info('Waiting for pwr_button to release, retry %d.', retry)
            retry += 1
            time.sleep(Servo.SHORT_DELAY)


    def lid_open(self):
        """Simulate opening the lid."""
        self.set_nocheck('lid_open', 'yes')


    def lid_close(self):
        """Simulate closing the lid.

        Waits 6 seconds to ensure the device is fully asleep before returning.
        """
        self.set_nocheck('lid_open', 'no')
        time.sleep(Servo.SLEEP_DELAY)


    def _press_and_release_keys(self, m1, m2,
                                press_secs=SERVO_KEY_PRESS_DELAY):
        """Simulate button presses."""
        # set keys to none
        (m2_a1, m2_a0) = self.KEY_MATRIX['m2']['none']
        (m1_a1, m1_a0) = self.KEY_MATRIX['m1']['none']
        self.set_nocheck('kbd_m2_a0', m2_a0)
        self.set_nocheck('kbd_m2_a1', m2_a1)
        self.set_nocheck('kbd_m1_a0', m1_a0)
        self.set_nocheck('kbd_m1_a1', m1_a1)

        (m2_a1, m2_a0) = self.KEY_MATRIX['m2'][m2]
        (m1_a1, m1_a0) = self.KEY_MATRIX['m1'][m1]
        self.set_nocheck('kbd_en', 'on')
        self.set_nocheck('kbd_m2_a0', m2_a0)
        self.set_nocheck('kbd_m2_a1', m2_a1)
        self.set_nocheck('kbd_m1_a0', m1_a0)
        self.set_nocheck('kbd_m1_a1', m1_a1)
        time.sleep(press_secs)
        self.set_nocheck('kbd_en', 'off')


    def ctrl_d(self):
        """Simulate Ctrl-d simultaneous button presses."""
        self._press_and_release_keys('d', 'ctrl')


    def ctrl_enter(self):
        """Simulate Ctrl-enter simultaneous button presses."""
        self._press_and_release_keys('enter', 'ctrl')


    def d_key(self):
        """Simulate Enter key button press."""
        self._press_and_release_keys('d', 'none')


    def ctrl_key(self):
        """Simulate Enter key button press."""
        self._press_and_release_keys('none', 'ctrl')


    def enter_key(self):
        """Simulate Enter key button press."""
        self._press_and_release_keys('enter', 'none')


    def refresh_key(self):
        """Simulate Refresh key (F3) button press."""
        self._press_and_release_keys('none', 'refresh')


    def ctrl_refresh_key(self):
        """Simulate Ctrl and Refresh (F3) simultaneous press.

        This key combination is an alternative of Space key.
        """
        self._press_and_release_keys('ctrl_r', 'refresh')


    def imaginary_key(self):
        """Simulate imaginary key button press.

        Maps to a key that doesn't physically exist.
        """
        self._press_and_release_keys('none', 'unused')


    def enable_recovery_mode(self):
        """Enable recovery mode on device."""
        self.set('rec_mode', 'on')


    def disable_recovery_mode(self):
        """Disable recovery mode on device."""
        self.set('rec_mode', 'off')


    def enable_development_mode(self):
        """Enable development mode on device."""
        self.set('dev_mode', 'on')


    def disable_development_mode(self):
        """Disable development mode on device."""
        self.set('dev_mode', 'off')

    def enable_usb_hub(self, host=False):
        """Enable Servo's USB/ethernet hub.

        This is equivalent to plugging in the USB devices attached to Servo to
        the host (if |host| is True) or dut (if |host| is False).
        For host=False, requires that the USB out on the servo board is
        connected to a USB in port on the target device. Servo's USB ports are
        labeled DUT_HUB_USB1 and DUT_HUB_USB2. Servo's ethernet port is also
        connected to this hub. Servo's USB port DUT_HUB_IN is the output of the
        hub.
        """
        self.set('dut_hub_pwren', 'on')
        if host:
            self.set('usb_mux_oe1', 'on')
            self.set('usb_mux_sel1', 'servo_sees_usbkey')
        else:
            self.set('dut_hub_sel', 'dut_sees_hub')

        self.set('dut_hub_on', 'yes')


    def disable_usb_hub(self):
        """Disable Servo's USB/ethernet hub.

        This is equivalent to unplugging the USB devices attached to Servo.
        """
        self.set('dut_hub_on', 'no')


    def boot_devmode(self):
        """Boot a dev-mode device that is powered off."""
        self.power_short_press()
        self.pass_devmode()


    def pass_devmode(self):
        """Pass through boot screens in dev-mode."""
        time.sleep(Servo.BOOT_DELAY)
        self.ctrl_d()
        time.sleep(Servo.BOOT_DELAY)


    def cold_reset(self):
        """Perform a cold reset of the EC.

        This has the side effect of shutting off the device.  The
        device is guaranteed to be off at the end of this call.
        """
        # After the reset, give the EC the time it needs to
        # re-initialize.
        self.set('cold_reset', 'on')
        time.sleep(Servo.SERVO_SEND_SIGNAL_DELAY)
        self.set('cold_reset', 'off')
        time.sleep(self._EC_RESET_DELAY)


    def warm_reset(self):
        """Perform a warm reset of the device.

        Has the side effect of restarting the device.
        """
        self.set('warm_reset', 'on')
        time.sleep(Servo.SERVO_SEND_SIGNAL_DELAY)
        self.set('warm_reset', 'off')


    def _get_xmlrpclib_exception(self, xmlexc):
        """Get meaningful exception string from xmlrpc.

        Args:
            xmlexc: xmlrpclib.Fault object

        xmlrpclib.Fault.faultString has the following format:

        <type 'exception type'>:'actual error message'

        Parse and return the real exception from the servod side instead of the
        less meaningful one like,
           <Fault 1: "<type 'exceptions.AttributeError'>:'tca6416' object has no
           attribute 'hw_driver'">

        Returns:
            string of underlying exception raised in servod.
        """
        return re.sub('^.*>:', '', xmlexc.faultString)


    def get(self, gpio_name):
        """Get the value of a gpio from Servod."""
        assert gpio_name
        try:
            return self._server.get(gpio_name)
        except  xmlrpclib.Fault as e:
            err_msg = "Getting '%s' :: %s" % \
                (gpio_name, self._get_xmlrpclib_exception(e))
            raise error.TestFail(err_msg)


    def set(self, gpio_name, gpio_value):
        """Set and check the value of a gpio using Servod."""
        self.set_nocheck(gpio_name, gpio_value)
        retry_count = Servo.GET_RETRY_MAX
        while gpio_value != self.get(gpio_name) and retry_count:
            logging.warn("%s != %s, retry %d", gpio_name, gpio_value,
                         retry_count)
            retry_count -= 1
            time.sleep(Servo.SHORT_DELAY)
        if not retry_count:
            assert gpio_value == self.get(gpio_name), \
                'Servo failed to set %s to %s' % (gpio_name, gpio_value)


    def set_nocheck(self, gpio_name, gpio_value):
        """Set the value of a gpio using Servod."""
        assert gpio_name and gpio_value
        logging.info('Setting %s to %s', gpio_name, gpio_value)
        try:
            self._server.set(gpio_name, gpio_value)
        except  xmlrpclib.Fault as e:
            err_msg = "Setting '%s' to '%s' :: %s" % \
                (gpio_name, gpio_value, self._get_xmlrpclib_exception(e))
            raise error.TestFail(err_msg)


    # TODO(waihong) It may fail if multiple servo's are connected to the same
    # host. Should look for a better way, like the USB serial name, to identify
    # the USB device.
    # TODO(sbasi) Remove this code from autoserv once firmware tests have been
    # updated.
    def probe_host_usb_dev(self):
        """Probe the USB disk device plugged-in the servo from the host side.

        It tries to switch the USB mux to make the host unable to see the
        USB disk and compares the result difference.

        This only works if the servo is attached to the local host.

        Returns:
          A string of USB disk path, like '/dev/sdb', or None if not existed.
        """
        cmd = 'ls /dev/sd[a-z]'
        original_value = self.get('usb_mux_sel1')

        # Make the host unable to see the USB disk.
        if original_value != 'dut_sees_usbkey':
            self.set('usb_mux_sel1', 'dut_sees_usbkey')
            time.sleep(self.USB_DETECTION_DELAY)
        no_usb_set = set(utils.system_output(cmd, ignore_status=True).split())

        # Make the host able to see the USB disk.
        self.set('usb_mux_sel1', 'servo_sees_usbkey')
        time.sleep(self.USB_DETECTION_DELAY)
        has_usb_set = set(utils.system_output(cmd, ignore_status=True).split())

        # Back to its original value.
        if original_value != 'servo_sees_usbkey':
            self.set('usb_mux_sel1', original_value)
            time.sleep(self.USB_DETECTION_DELAY)

        diff_set = has_usb_set - no_usb_set
        if len(diff_set) == 1:
            return diff_set.pop()
        else:
            return None


    def image_to_servo_usb(self, image_path=None,
                           make_image_noninteractive=False):
        """Install an image to the USB key plugged into the servo.

        This method may copy any image to the servo USB key including a
        recovery image or a test image.  These images are frequently used
        for test purposes such as restoring a corrupted image or conducting
        an upgrade of ec/fw/kernel as part of a test of a specific image part.

        Args:
            image_path: Path on the host to the recovery image.
            make_image_noninteractive: Make the recovery image noninteractive,
                                       therefore the DUT will reboot
                                       automatically after installation.
        """
        # Turn the device off. This should happen before USB key detection, to
        # prevent a recovery destined DUT from sensing the USB key due to the
        # autodetection procedure.
        self.initialize_dut(cold_reset=True)

        # Set up Servo's usb mux.
        self.set('prtctl4_pwren', 'on')
        self.enable_usb_hub(host=True)
        if image_path:
            logging.info('Searching for usb device and copying image to it.')
            if not self._server.download_image_to_usb(image_path):
                logging.error('Failed to transfer requested image to USB. '
                              'Please take a look at Servo Logs.')
                raise error.AutotestError('Download image to usb failed.')
            if make_image_noninteractive:
                logging.info('Making image noninteractive')
                if not self._server.make_image_noninteractive():
                    logging.error('Failed to make image noninteractive. '
                                  'Please take a look at Servo Logs.')


    def install_recovery_image(self, image_path=None,
                               wait_timeout=RECOVERY_INSTALL_DELAY,
                               make_image_noninteractive=False,
                               host=None):
        """Install the recovery image specied by the path onto the DUT.

        This method uses google recovery mode to install a recovery image
        onto a DUT through the use of a USB stick that is mounted on a servo
        board specified by the usb_dev.  If no image path is specified
        we use the recovery image already on the usb image.

        Args:
            image_path: Path on the host to the recovery image.
            wait_timeout: How long to wait for completion; default is
                          determined by a constant.
            make_image_noninteractive: Make the recovery image noninteractive,
                                       therefore the DUT will reboot
                                       automatically after installation.
            host: Host object for the DUT that the installation process is
                  running on. If provided, will wait to see if the host is back
                  up after starting recovery mode.
        """
        self.image_to_servo_usb(image_path, make_image_noninteractive)

        # Boot in recovery mode.
        try:
            self.enable_recovery_mode()
            self.power_short_press()
            time.sleep(Servo.RECOVERY_BOOT_DELAY)
            self.set('usb_mux_sel1', 'dut_sees_usbkey')
            self.disable_recovery_mode()

            if host:
                logging.info('Running the recovery process on the DUT. '
                             'Will wait up to %d seconds for recovery to '
                             'complete.', wait_timeout)
                start_time = time.time()
                # Wait for the host to come up.
                if host.wait_up(timeout=wait_timeout):
                    logging.info('Recovery process completed successfully in '
                                 '%d seconds.', time.time() - start_time)
                else:
                    logger.error('Host failed to come back up in the allotted '
                                 'time: %d seconds.', wait_timeout)
                logging.info('Removing the usb key from the DUT.')
                self.disable_usb_hub()
        except:
            # In case anything went wrong we want to make sure to do a clean
            # reset.
            self.disable_recovery_mode()
            self.warm_reset()
            raise


    def _connect_servod(self, servo_host, servo_port):
        """Connect to the Servod process with XMLRPC.

        Args:
          servo_port: Port the Servod process is listening on.
        """
        remote = 'http://%s:%s' % (servo_host, servo_port)
        self._server = xmlrpclib.ServerProxy(remote)
        try:
            self._server.echo("ping-test")
        except:
            logging.error('Connection to servod failed')
            raise
