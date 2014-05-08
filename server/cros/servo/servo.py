# Copyright (c) 2012 The Chromium OS Authors. All rights reserved.
# Use of this source code is governed by a BSD-style license that can be
# found in the LICENSE file.
#
# Expects to be run in an environment with sudo and no interactive password
# prompt, such as within the Chromium OS development chroot.

import os

import logging, re, time, xmlrpclib

from autotest_lib.client.common_lib import error
from autotest_lib.server import utils
from autotest_lib.server.cros.servo import power_state_controller
from autotest_lib.server.cros.servo import firmware_programmer


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
    SHORT_DELAY = 0.1

    # Maximum number of times to re-read power button on release.
    GET_RETRY_MAX = 10

    # Delays to deal with DUT state transitions.
    SLEEP_DELAY = 6
    BOOT_DELAY = 10

    # Default minimum time interval between 'press' and 'release'
    # keyboard events.
    SERVO_KEY_PRESS_DELAY = 0.1

    # Time between an usb disk plugged-in and detected in the system.
    USB_DETECTION_DELAY = 10
    # Time to keep USB power off before and after USB mux direction is changed
    USB_POWEROFF_DELAY = 2

    # Time to wait before timing out on servo initialization.
    INIT_TIMEOUT_SECS = 10


    def __init__(self, servo_host, servo_serial=None):
        """Sets up the servo communication infrastructure.

        @param servo_host: A ServoHost object representing
                           the host running servod.
        @param servo_serial: Serial number of the servo board.
        """
        # TODO(fdeng): crbug.com/298379
        # We should move servo_host object out of servo object
        # to minimize the dependencies on the rest of Autotest.
        self._servo_host = servo_host
        self._servo_serial = servo_serial
        self._server = servo_host.get_servod_server_proxy()
        board = self._server.get_board()
        self._power_state = (
            power_state_controller.create_controller(self, board))

        # a string, showing what interface (host or dut) the USB device is
        # connected to.
        self._usb_state = None
        self.set('dut_hub_pwren', 'on')
        self.set('usb_mux_oe1', 'on')
        self.switch_usbkey('off')

        # Initialize firmware programmer
        if self.get_version() == "servo_v2":
            self._programmer = firmware_programmer.ProgrammerV2(self)
        else:
            logging.warning("No firmware programmer for servo version: %s",
                         self.get_version())


    @property
    def servo_serial(self):
        """Returns the serial number of the servo board."""
        return self._servo_serial


    def get_power_state_controller(self):
        """Return the power state controller for this Servo.

        The power state controller provides board-independent
        interfaces for reset, power-on, power-off operations.

        """
        return self._power_state


    def initialize_dut(self, cold_reset=False):
        """Initializes a dut for testing purposes.

        This sets various servo signals back to default values
        appropriate for the target board.  By default, if the DUT
        is already on, it stays on.  If the DUT is powered off
        before initialization, its state afterward is unspecified.

        Rationale:  Basic initialization of servo sets the lid open,
        when there is a lid.  This operation won't affect powered on
        units; however, setting the lid open may power on a unit
        that's off, depending on the board type and previous state
        of the device.

        If `cold_reset` is a true value, cold reset will be applied
        to the DUT.  Cold reset will force the DUT to power off;
        however, the final state of the DUT depends on the board type.

        @param cold_reset If True, cold reset the device after
                          initialization.
        """
        self._server.hwinit()
        if cold_reset:
            self._power_state.cold_reset()


    def is_localhost(self):
        """Is the servod hosted locally?

        Returns:
          True if local hosted; otherwise, False.
        """
        return self._servo_host.is_localhost()


    def power_long_press(self):
        """Simulate a long power button press."""
        # After a long power press, the EC may ignore the next power
        # button press (at least on Alex).  To guarantee that this
        # won't happen, we need to allow the EC one second to
        # collect itself.
        self._server.power_long_press()


    def power_normal_press(self):
        """Simulate a normal power button press."""
        self._server.power_normal_press()


    def power_short_press(self):
        """Simulate a short power button press."""
        self._server.power_short_press()


    def power_key(self, press_secs=''):
        """Simulate a power button press.

        @param press_secs : Str. Time to press key.
        """
        self._server.power_key(press_secs)


    def lid_open(self):
        """Simulate opening the lid."""
        self.set_nocheck('lid_open', 'yes')


    def lid_close(self):
        """Simulate closing the lid.

        Waits 6 seconds to ensure the device is fully asleep before returning.
        """
        self.set_nocheck('lid_open', 'no')
        time.sleep(Servo.SLEEP_DELAY)


    def ctrl_d(self, press_secs=''):
        """Simulate Ctrl-d simultaneous button presses.

        @param press_secs : Str. Time to press key.
        """
        self._server.ctrl_d(press_secs)


    def ctrl_u(self):
        """Simulate Ctrl-u simultaneous button presses.

        @param press_secs : Str. Time to press key.
        """
        self._server.ctrl_u()


    def ctrl_enter(self, press_secs=''):
        """Simulate Ctrl-enter simultaneous button presses.

        @param press_secs : Str. Time to press key.
        """
        self._server.ctrl_enter(press_secs)


    def d_key(self, press_secs=''):
        """Simulate Enter key button press.

        @param press_secs : Str. Time to press key.
        """
        self._server.d_key(press_secs)


    def ctrl_key(self, press_secs=''):
        """Simulate Enter key button press.

        @param press_secs : Str. Time to press key.
        """
        self._server.ctrl_key(press_secs)


    def enter_key(self, press_secs=''):
        """Simulate Enter key button press.

        @param press_secs : Str. Time to press key.
        """
        self._server.enter_key(press_secs)


    def refresh_key(self, press_secs=''):
        """Simulate Refresh key (F3) button press.

        @param press_secs : Str. Time to press key.
        """
        self._server.refresh_key(press_secs)


    def ctrl_refresh_key(self, press_secs=''):
        """Simulate Ctrl and Refresh (F3) simultaneous press.

        This key combination is an alternative of Space key.

        @param press_secs : Str. Time to press key.
        """
        self._server.ctrl_refresh_key(press_secs)


    def imaginary_key(self, press_secs=''):
        """Simulate imaginary key button press.

        Maps to a key that doesn't physically exist.

        @param press_secs : Str. Time to press key.
        """
        self._server.imaginary_key(press_secs)


    def enable_recovery_mode(self):
        """Enable recovery mode on device."""
        self.set('rec_mode', 'on')


    def custom_recovery_mode(self):
        """Custom key combination to enter recovery mode."""
        self._press_keys('rec_mode')
        self.power_normal_press()
        time.sleep(self.SERVO_KEY_PRESS_DELAY)
        self.set_nocheck('kbd_en', 'off')


    def disable_recovery_mode(self):
        """Disable recovery mode on device."""
        self.set('rec_mode', 'off')


    def enable_development_mode(self):
        """Enable development mode on device."""
        self.set('dev_mode', 'on')


    def disable_development_mode(self):
        """Disable development mode on device."""
        self.set('dev_mode', 'off')

    def boot_devmode(self):
        """Boot a dev-mode device that is powered off."""
        self.power_short_press()
        self.pass_devmode()


    def pass_devmode(self):
        """Pass through boot screens in dev-mode."""
        time.sleep(Servo.BOOT_DELAY)
        self.ctrl_d()
        time.sleep(Servo.BOOT_DELAY)


    def get_version(self):
        """Get the version of servod board.

        """
        return self._server.get_version()


    def get_board(self):
        """Get the board connected to servod.

        """
        return self._server.get_board()


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
            logging.warning("%s != %s, retry %d", gpio_name, gpio_value,
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


    def set_get_all(self, controls):
        """Set &| get one or more control values.

        @param controls: list of strings, controls to set &| get.

        @raise: error.TestError in case error occurs setting/getting values.
        """
        rv = []
        try:
            logging.info('Set/get all: %s', str(controls))
            rv = self._server.set_get_all(controls)
        except xmlrpclib.Fault as e:
            # TODO(waihong): Remove the following backward compatibility when
            # the new versions of hdctools are deployed.
            if 'not supported' in str(e):
                logging.warning('The servod is too old that set_get_all '
                        'not supported. Use set and get instead.')
                for control in controls:
                    if ':' in control:
                        (name, value) = control.split(':')
                        if name == 'sleep':
                            time.sleep(float(value))
                        else:
                            self.set_nocheck(name, value)
                        rv.append(True)
                    else:
                        rv.append(self.get(name))
            else:
                err_msg = "Problem with '%s' :: %s" % \
                    (controls, self._get_xmlrpclib_exception(e))
                raise error.TestFail(err_msg)
        return rv


    # TODO(waihong) It may fail if multiple servo's are connected to the same
    # host. Should look for a better way, like the USB serial name, to identify
    # the USB device.
    # TODO(sbasi) Remove this code from autoserv once firmware tests have been
    # updated.
    def probe_host_usb_dev(self):
        """Probe the USB disk device plugged-in the servo from the host side.

        It tries to switch the USB mux to make the host unable to see the
        USB disk and compares the result difference.

        Returns:
          A string of USB disk path, like '/dev/sdb', or None if not existed.
        """
        cmd = 'ls /dev/sd[a-z]'
        original_value = self.get_usbkey_direction()

        # Make the host unable to see the USB disk.
        self.switch_usbkey('off')
        no_usb_set = set(self.system_output(cmd, ignore_status=True).split())

        # Make the host able to see the USB disk.
        self.switch_usbkey('host')
        has_usb_set = set(self.system_output(cmd, ignore_status=True).split())

        # Back to its original value.
        if original_value != self.get_usbkey_direction():
            self.switch_usbkey(original_value)

        diff_set = has_usb_set - no_usb_set
        if len(diff_set) == 1:
            return diff_set.pop()
        else:
            return None


    def recovery_supported(self):
        """Return whether servo-based recovery should work.

        Use of `image_to_servo_usb()` and `install_recovery_image()`
        relies on DUT-board specific behaviors, and is not supported
        for all types of board.  Return whether these two operations
        are expected to succeed for the current DUT.

        @return `True` iff the recovery related methods are supported
                for this servo and DUT.

        """
        return self._power_state.recovery_supported()


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
        # We're about to start plugging/unplugging the USB key.  We
        # don't know the state of the DUT, or what it might choose
        # to do to the device after hotplug.  To avoid surprises,
        # force the DUT to be off.
        self._server.hwinit()
        self._power_state.power_off()

        # Set up Servo's usb mux.
        self.switch_usbkey('host')
        if image_path:
            logging.info('Searching for usb device and copying image to it. '
                         'Please wait a few minutes...')
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
                               make_image_noninteractive=False):
        """Install the recovery image specied by the path onto the DUT.

        This method uses google recovery mode to install a recovery image
        onto a DUT through the use of a USB stick that is mounted on a servo
        board specified by the usb_dev.  If no image path is specified
        we use the recovery image already on the usb image.

        Args:
            image_path: Path on the host to the recovery image.
            make_image_noninteractive: Make the recovery image noninteractive,
                                       therefore the DUT will reboot
                                       automatically after installation.
        """
        self.image_to_servo_usb(image_path, make_image_noninteractive)
        self._power_state.power_on(rec_mode=power_state_controller.REC_ON)
        self.switch_usbkey('dut')


    def _scp_image(self, image_path):
        """Copy image to the servo host.

        When programming a firmware image on the DUT, the image must be
        located on the host to which the servo device is connected. Sometimes
        servo is controlled by a remote host, in this case the image needs to
        be transferred to the remote host.

        @param image_path: a string, name of the firmware image file to be
               transferred.
        @return: a string, full path name of the copied file on the remote.
        """

        dest_path = os.path.join('/tmp', os.path.basename(image_path))
        self._servo_host.send_file(image_path, dest_path)
        return dest_path


    def system(self, command, timeout=None):
        """Execute the passed in command on the servod host."""
        logging.info('Will execute on servo host: %s', command)
        self._servo_host.run(command, timeout=timeout)


    def system_output(self, command, timeout=None,
                      ignore_status=False, args=()):
        """Execute the passed in command on the servod host, return stdout.

        @param command, a string, the command to execute
        @param timeout, an int, max number of seconds to wait til command
               execution completes
        @ignore_status, a Boolean, if true - ignore command's nonzero exit
               status, otherwise an exception will be thrown
        @param args, a tuple of strings, each becoming a separate command line
               parameter for the command
        @return: command's stdout as a string.
        """
        logging.info('Will execute and collect output on servo host: %s %s',
                     command, ' '.join("'%s'" % x for x in args))
        return self._servo_host.run(command, timeout=timeout,
                                    ignore_status=ignore_status,
                                    args=args).stdout.strip()


    def program_bios(self, image):
        """Program bios on DUT with given image.

        @param image: a string, file name of the BIOS image to program
                      on the DUT.

        """
        if not self.is_localhost():
            image = self._scp_image(image)
        self._programmer.program_bios(image)


    def program_ec(self, image):
        """Program ec on DUT with given image.

        @param image: a string, file name of the EC image to program
                      on the DUT.

        """
        if not self.is_localhost():
            image = self._scp_image(image)
        self._programmer.program_ec(image)


    def _switch_usbkey_power(self, power_state, detection_delay=False):
        """Switch usbkey power.

        This function switches usbkey power by setting the value of
        'prtctl4_pwren'. If the power is already in the
        requested state, this function simply returns.

        @param power_state: A string, 'on' or 'off'.
        @param detection_delay: A boolean value, if True, sleep
                                for |USB_DETECTION_DELAY| after switching
                                the power on.
        """
        self.set('prtctl4_pwren', power_state)
        if power_state == 'off':
            time.sleep(self.USB_POWEROFF_DELAY)
        elif detection_delay:
            time.sleep(self.USB_DETECTION_DELAY)


    def switch_usbkey(self, usb_state):
        """Connect USB flash stick to either host or DUT, or turn USB port off.

        This function switches the servo multiplexer to provide electrical
        connection between the USB port J3 and either host or DUT side. It
        can also be used to turn the USB port off.

        Switching to 'dut' or 'host' is accompanied by powercycling
        of the USB stick, because it sometimes gets wedged if the mux
        is switched while the stick power is on.

        @param usb_state: A string, one of 'dut', 'host', or 'off'.
                          'dut' and 'host' indicate which side the
                          USB flash device is required to be connected to.
                          'off' indicates turning the USB port off.

        @raise: error.TestError in case the parameter is not 'dut'
                'host', or 'off'.
        """
        if self.get_usbkey_direction() == usb_state:
            return

        if usb_state == 'off':
           self._switch_usbkey_power('off')
           self._usb_state = usb_state
           return
        elif usb_state == 'host':
            mux_direction = 'servo_sees_usbkey'
        elif usb_state == 'dut':
            mux_direction = 'dut_sees_usbkey'
        else:
            raise error.TestError('Unknown USB state request: %s' % usb_state)

        self._switch_usbkey_power('off')
        self.set('usb_mux_sel1', mux_direction)
        time.sleep(self.USB_POWEROFF_DELAY)
        self._switch_usbkey_power('on', usb_state == 'host')
        self._usb_state = usb_state


    def get_usbkey_direction(self):
        """Get which side USB is connected to or 'off' if usb power is off.

        @return: A string, one of 'dut', 'host', or 'off'.
        """
        if not self._usb_state:
            if self.get('prtctl4_pwren') == 'off':
                self._usb_state = 'off'
            elif self.get('usb_mux_sel1').startswith('dut'):
                self._usb_state = 'dut'
            else:
                self._usb_state = 'host'
        return self._usb_state
