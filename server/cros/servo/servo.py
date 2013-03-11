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
from autotest_lib.server.cros.servo import programmer


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

    # Time in seconds to allow the firmware to initialize itself and
    # present the "INSERT" screen in recovery mode before actually
    # inserting a USB stick to boot from.
    _RECOVERY_INSERT_DELAY = 10.0

    # Minimum time in seconds to hold the "cold_reset" or
    # "warm_reset" signals asserted.
    _DUT_RESET_DELAY = 0.5

    # Time required for the EC to be working after cold reset.
    # Five seconds is at least twice as big as necessary for Alex,
    # and is presumably good enough for all future systems.
    _EC_RESET_DELAY = 5.0

    # Default minimum time interval between 'press' and 'release'
    # keyboard events.
    SERVO_KEY_PRESS_DELAY = 0.1

    # Time between an usb disk plugged-in and detected in the system.
    USB_DETECTION_DELAY = 10
    # Time to keep USB power off before and after USB mux direction is changed
    USB_POWEROFF_DELAY = 2

    KEY_MATRIX_ALT_0 = {
        'ctrl_refresh':  ['0', '0', '0', '1'],
        'ctrl_d':        ['0', '1', '0', '0'],
        'd':             ['0', '1', '1', '1'],
        'ctrl_enter':    ['1', '0', '0', '0'],
        'enter':         ['1', '0', '1', '1'],
        'ctrl':          ['1', '1', '0', '0'],
        'refresh':       ['1', '1', '0', '1'],
        'unused':        ['1', '1', '1', '0'],
        'none':          ['1', '1', '1', '1']}

    KEY_MATRIX_ALT_1 = {
        'ctrl_d':        ['0', '0', '1', '0'],
        'd':             ['0', '0', '1', '1'],
        'ctrl_enter':    ['0', '1', '1', '0'],
        'enter':         ['0', '1', '1', '1'],
        'ctrl_refresh':  ['1', '0', '0', '1'],
        'unused':        ['1', '1', '0', '0'],
        'refresh':       ['1', '1', '0', '1'],
        'ctrl':          ['1', '1', '1', '0'],
        'none':          ['1', '1', '1', '1']}

    KEY_MATRIX_ALT_2 = {
        'ctrl_d':        ['0', '0', '0', '1'],
        'd':             ['0', '0', '1', '1'],
        'unused':        ['0', '1', '1', '1'],
        'rec_mode':      ['1', '0', '0', '0'],
        'ctrl_enter':    ['1', '0', '0', '1'],
        'enter':         ['1', '0', '1', '1'],
        'ctrl':          ['1', '1', '0', '1'],
        'refresh':       ['1', '1', '1', '0'],
        'ctrl_refresh':  ['1', '1', '1', '1'],
        'none':          ['1', '1', '1', '1']}

    KEY_MATRIX = [KEY_MATRIX_ALT_0, KEY_MATRIX_ALT_1, KEY_MATRIX_ALT_2]

    def __init__(self, servo_host='localhost', servo_port=9999):
        """Sets up the servo communication infrastructure.

        @param servo_host  Name of the host where the servod process
                           is running.
        @param servo_port  Port the servod process is listening on.
        """
        self._key_matrix = 0
        self._server = None
        self._connect_servod(servo_host, servo_port)
        self._is_localhost = (servo_host == 'localhost')
        self._power_state = power_state_controller.PowerStateController(self)

        # a string, showing what interface (host or dut) the USB device is
        # connected to.
        self._usb_position = None
        self.set('dut_hub_pwren', 'on')
        self.set('usb_mux_oe1', 'on')
        self.switch_usbkey('host')

        # Commands on the servo host must be run by the superuser. Our account
        # on Beaglebone is root, but locally we might be running as a
        # different user. If so - `sudo ' will have to be added to the
        # commands.
        if self._is_localhost:
            self._sudo_required = utils.system_output('id -u') != '0'
            self._ssh_prefix = ''
        else:
            common_options = '-o PasswordAuthentication=no'
            self._sudo_required = False
            self._ssh_prefix = 'ssh %s root@%s ' % (common_options, servo_host)
            self._scp_cmd_template = 'scp -r %s ' % common_options
            self._scp_cmd_template += '%s ' + 'root@' + servo_host + ':%s'

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


    def is_localhost(self):
        """Is the servod hosted locally?

        Returns:
          True if local hosted; otherwise, False.
        """
        return self._is_localhost


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


    def _press_keys(self, key):
        """Simulate button presses.

        Note, key presses will remain on indefinitely. See
            _press_and_release_keys for release procedure.
        """
        (m1_a1, m1_a0, m2_a1, m2_a0) = self.KEY_MATRIX[self._key_matrix]['none']
        self.set_nocheck('kbd_m2_a0', m2_a0)
        self.set_nocheck('kbd_m2_a1', m2_a1)
        self.set_nocheck('kbd_m1_a0', m1_a0)
        self.set_nocheck('kbd_m1_a1', m1_a1)
        self.set_nocheck('kbd_en', 'on')

        (m1_a1, m1_a0, m2_a1, m2_a0) = self.KEY_MATRIX[self._key_matrix][key]
        self.set_nocheck('kbd_m2_a0', m2_a0)
        self.set_nocheck('kbd_m2_a1', m2_a1)
        self.set_nocheck('kbd_m1_a0', m1_a0)
        self.set_nocheck('kbd_m1_a1', m1_a1)


    def _press_and_release_keys(self, key,
                                press_secs=SERVO_KEY_PRESS_DELAY):
        """Simulate button presses and release."""
        self._press_keys(key)
        time.sleep(press_secs)
        self.set_nocheck('kbd_en', 'off')


    def set_key_matrix(self, matrix=0):
        """Set keyboard mapping"""
        self._key_matrix = matrix


    def ctrl_d(self):
        """Simulate Ctrl-d simultaneous button presses."""
        self._press_and_release_keys('ctrl_d')


    def ctrl_enter(self):
        """Simulate Ctrl-enter simultaneous button presses."""
        self._press_and_release_keys('ctrl_enter')


    def d_key(self):
        """Simulate Enter key button press."""
        self._press_and_release_keys('d')


    def ctrl_key(self):
        """Simulate Enter key button press."""
        self._press_and_release_keys('ctrl')


    def enter_key(self):
        """Simulate Enter key button press."""
        self._press_and_release_keys('enter')


    def refresh_key(self):
        """Simulate Refresh key (F3) button press."""
        self._press_and_release_keys('refresh')


    def ctrl_refresh_key(self):
        """Simulate Ctrl and Refresh (F3) simultaneous press.

        This key combination is an alternative of Space key.
        """
        self._press_and_release_keys('ctrl_refresh')


    def imaginary_key(self):
        """Simulate imaginary key button press.

        Maps to a key that doesn't physically exist.
        """
        self._press_and_release_keys('unused')


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


    def cold_reset(self):
        """Perform a cold reset of the EC.

        This has the side effect of shutting off the device.  The
        device is guaranteed to be off at the end of this call.
        """
        # After the reset, give the EC the time it needs to
        # re-initialize.
        self.set('cold_reset', 'on')
        time.sleep(self._DUT_RESET_DELAY)
        self.set('cold_reset', 'off')
        time.sleep(self._EC_RESET_DELAY)


    def warm_reset(self):
        """Perform a warm reset of the device.

        Has the side effect of restarting the device.
        """
        self.set('warm_reset', 'on')
        time.sleep(self._DUT_RESET_DELAY)
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

        Returns:
          A string of USB disk path, like '/dev/sdb', or None if not existed.
        """
        cmd = 'ls /dev/sd[a-z]'
        original_value = self.get_usbkey_direction()

        # Make the host unable to see the USB disk.
        if original_value != 'dut':
            self.switch_usbkey('dut')
            time.sleep(self.USB_DETECTION_DELAY)
        no_usb_set = set(self.system_output(cmd, ignore_status=True).split())

        # Make the host able to see the USB disk.
        self.switch_usbkey('host')
        time.sleep(self.USB_DETECTION_DELAY)
        has_usb_set = set(self.system_output(cmd, ignore_status=True).split())

        # Back to its original value.
        if original_value != self.get_usbkey_direction():
            self.switch_usbkey(original_value)
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
        # We're about to start plugging/unplugging the USB key.  We
        # don't know the state of the DUT, or what it might choose
        # to do to the device after hotplug.  To avoid surprises,
        # force the DUT to be off.
        self._server.hwinit()
        self._power_state.power_off()

        # Set up Servo's usb mux.
        self.set('prtctl4_pwren', 'on')
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
        self._power_state.power_on(dev_mode=self._power_state.DEV_OFF,
                                   rec_mode=self._power_state.REC_ON)
        time.sleep(self._RECOVERY_INSERT_DELAY)
        self.switch_usbkey('dut')


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
        scp_cmd = self._scp_cmd_template % (image_path, dest_path)
        utils.system(scp_cmd)
        return dest_path


    def system(self, command, timeout=None):
        """Execute the passed in command on the servod host."""
        if self._sudo_required:
            command = 'sudo -n %s' % command
        if self._ssh_prefix:
            command = "%s '%s'" % (self._ssh_prefix, command)
        logging.info('Will execute on servo host: %s', command)
        utils.system(command, timeout=timeout)


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
        if self._sudo_required:
            command = 'sudo -n %s' % command
        if self._ssh_prefix:
            command = "%s '%s'" % (self._ssh_prefix, command)
        logging.info('Will execute and collect output on servo host: %s %s',
                     command, ' '.join("'%s'" % x for x in args))
        return utils.system_output(command, timeout=timeout,
                                   ignore_status=ignore_status, args=args)


    def program_ec(self, board, image):
        """Program EC on a given board using given image.

        @param board: a string, type of the DUT board
        @param image: a string, file name of the EC image to program on the
                      DUT
        """
        if not self.is_localhost():
            image = self._scp_image(image)
        programmer.program_ec(board, self, image)


    def program_bootprom(self, board, image):
        """Program bootprom on a given board using given image.

        In case servo is controlled by a remote host, the image needs to be
        transferred to the host.

        If the device tree subdirectory is present along with the image, the
        subdirectory is also copied to the remote host.

        @param board: a string, type of the DUT board
        @param image: a string, file name of the firmware image to program on
                      the DUT. The device tree subdirectory, if present, is on
                      the same level with the image file.
        """
        if not self.is_localhost():
            dts_path = os.path.join(os.path.dirname(image), 'dts')
            image = self._scp_image(image)
            if os.path.isdir(dts_path):
                self._scp_image(dts_path)
        programmer.program_bootprom(board, self, image)

    def switch_usbkey(self, side):
        """Connect USB flash stick to either host or DUT.

        This function switches the servo multiplexer to provide electrical
        connection between the USB port J3 and either host or DUT side.

        Switching is accompanied by powercycling of the USB stick, because it
        sometimes gets wedged if the mux is switched while the stick power is
        on.

        @param side: a string, either 'dut' or 'host' - indicates which side
                   the USB flash device is required to be connected to.

        @raise: error.TestError in case the parameter is neither 'dut' not
                   'host'
        """

        if self._usb_position == side:
            return

        if side == 'host':
            mux_direction = 'servo_sees_usbkey'
        elif side == 'dut':
            mux_direction = 'dut_sees_usbkey'
        else:
            raise error.TestError('unknown USB mux setting: %s' % side)

        self.set('prtctl4_pwren', 'off')
        time.sleep(self.USB_POWEROFF_DELAY)
        self.set('usb_mux_sel1', mux_direction)
        time.sleep(self.USB_POWEROFF_DELAY)
        self.set('prtctl4_pwren', 'on')

        self._usb_position = side


    def get_usbkey_direction(self):
        """Get name of the side the USB device is connected to.

        @return a string, either 'dut' or 'host'
        """
        if not self._usb_position:
            if self.get('usb_mux_sel1').starstwith('dut'):
                self._usb_position = 'dut'
            else:
                self._usb_position = 'host'
        return self._usb_position
