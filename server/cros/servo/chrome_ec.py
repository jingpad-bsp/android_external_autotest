# Copyright (c) 2012 The Chromium OS Authors. All rights reserved.
# Use of this source code is governed by a BSD-style license that can be
# found in the LICENSE file.

import ast
import functools
import logging
import re
import time

from autotest_lib.client.bin import utils
from autotest_lib.client.common_lib import error
from autotest_lib.client.cros import ec

# Hostevent codes, copied from:
#     ec/include/ec_commands.h
HOSTEVENT_LID_CLOSED        = 0x00000001
HOSTEVENT_LID_OPEN          = 0x00000002
HOSTEVENT_POWER_BUTTON      = 0x00000004
HOSTEVENT_AC_CONNECTED      = 0x00000008
HOSTEVENT_AC_DISCONNECTED   = 0x00000010
HOSTEVENT_BATTERY_LOW       = 0x00000020
HOSTEVENT_BATTERY_CRITICAL  = 0x00000040
HOSTEVENT_BATTERY           = 0x00000080
HOSTEVENT_THERMAL_THRESHOLD = 0x00000100
HOSTEVENT_THERMAL_OVERLOAD  = 0x00000200
HOSTEVENT_THERMAL           = 0x00000400
HOSTEVENT_USB_CHARGER       = 0x00000800
HOSTEVENT_KEY_PRESSED       = 0x00001000
HOSTEVENT_INTERFACE_READY   = 0x00002000
# Keyboard recovery combo has been pressed
HOSTEVENT_KEYBOARD_RECOVERY = 0x00004000
# Shutdown due to thermal overload
HOSTEVENT_THERMAL_SHUTDOWN  = 0x00008000
# Shutdown due to battery level too low
HOSTEVENT_BATTERY_SHUTDOWN  = 0x00010000
HOSTEVENT_INVALID           = 0x80000000

# Time to wait after sending keypress commands.
KEYPRESS_RECOVERY_TIME = 0.5


class ChromeConsole(object):
    """Manages control of a Chrome console.

    We control the Chrome console via the UART of a Servo board. Chrome console
    provides many interfaces to set and get its behavior via console commands.
    This class is to abstract these interfaces.
    """

    CMD = "_cmd"
    REGEXP = "_regexp"
    MULTICMD = "_multicmd"

    def __init__(self, servo, name):
        """Initialize and keep the servo object.

        Args:
          servo: A Servo object.
          name: The console name.
        """
        self.name = name
        self.uart_cmd = self.name + self.CMD
        self.uart_regexp = self.name + self.REGEXP
        self.uart_multicmd = self.name + self.MULTICMD

        self._servo = servo
        self._cached_uart_regexp = None


    def set_uart_regexp(self, regexp):
        if self._cached_uart_regexp == regexp:
            return
        self._cached_uart_regexp = regexp
        self._servo.set(self.uart_regexp, regexp)


    def send_command(self, commands):
        """Send command through UART.

        This function opens UART pty when called, and then command is sent
        through UART.

        Args:
          commands: The commands to send, either a list or a string.
        """
        self.set_uart_regexp('None')
        if isinstance(commands, list):
            try:
                self._servo.set_nocheck(self.uart_multicmd, ';'.join(commands))
            except error.TestFail as e:
                if 'No control named' in str(e):
                    logging.warning(
                            'The servod is too old that uart_multicmd '
                            'not supported. Use uart_cmd instead.')
                    for command in commands:
                        self._servo.set_nocheck(self.uart_cmd, command)
                else:
                    raise
        else:
            self._servo.set_nocheck(self.uart_cmd, commands)


    def send_command_get_output(self, command, regexp_list):
        """Send command through UART and wait for response.

        This function waits for response message matching regular expressions.

        Args:
          command: The command sent.
          regexp_list: List of regular expressions used to match response
            message. Note, list must be ordered.

        Returns:
          List of tuples, each of which contains the entire matched string and
          all the subgroups of the match. None if not matched.
          For example:
            response of the given command:
              High temp: 37.2
              Low temp: 36.4
            regexp_list:
              ['High temp: (\d+)\.(\d+)', 'Low temp: (\d+)\.(\d+)']
            returns:
              [('High temp: 37.2', '37', '2'), ('Low temp: 36.4', '36', '4')]

        Raises:
          error.TestError: An error when the given regexp_list is not valid.
        """
        if not isinstance(regexp_list, list):
            raise error.TestError('Arugment regexp_list is not a list: %s' %
                                  str(regexp_list))

        self.set_uart_regexp(str(regexp_list))
        self._servo.set_nocheck(self.uart_cmd, command)
        return ast.literal_eval(self._servo.get(self.uart_cmd))


class ChromeEC(ChromeConsole):
    """Manages control of a Chrome EC.

    We control the Chrome EC via the UART of a Servo board. Chrome EC
    provides many interfaces to set and get its behavior via console commands.
    This class is to abstract these interfaces.
    """

    def __init__(self, servo, name="ec_uart"):
        super(ChromeEC, self).__init__(servo, name)


    def key_down(self, keyname):
        """Simulate pressing a key.

        Args:
          keyname: Key name, one of the keys of KEYMATRIX.
        """
        self.send_command('kbpress %d %d 1' %
                (ec.KEYMATRIX[keyname][1], ec.KEYMATRIX[keyname][0]))


    def key_up(self, keyname):
        """Simulate releasing a key.

        Args:
          keyname: Key name, one of the keys of KEYMATRIX.
        """
        self.send_command('kbpress %d %d 0' %
                (ec.KEYMATRIX[keyname][1], ec.KEYMATRIX[keyname][0]))


    def key_press(self, keyname):
        """Press and then release a key.

        Args:
          keyname: Key name, one of the keys of KEYMATRIX.
        """
        self.send_command([
                'kbpress %d %d 1' %
                    (ec.KEYMATRIX[keyname][1], ec.KEYMATRIX[keyname][0]),
                'kbpress %d %d 0' %
                    (ec.KEYMATRIX[keyname][1], ec.KEYMATRIX[keyname][0]),
                ])
        # Don't spam the EC console as fast as we can; leave some recovery time
        # in between commands.
        time.sleep(KEYPRESS_RECOVERY_TIME)


    def send_key_string_raw(self, string):
        """Send key strokes consisting of only characters.

        Args:
          string: Raw string.
        """
        for c in string:
            self.key_press(c)


    def send_key_string(self, string):
        """Send key strokes including special keys.

        Args:
          string: Character string including special keys. An example
            is "this is an<tab>example<enter>".
        """
        for m in re.finditer("(<[^>]+>)|([^<>]+)", string):
            sp, raw = m.groups()
            if raw is not None:
                self.send_key_string_raw(raw)
            else:
                self.key_press(sp)


    def reboot(self, flags=''):
        """Reboot EC with given flags.

        Args:
          flags: Optional, a space-separated string of flags passed to the
                 reboot command, including:
                   default: EC soft reboot;
                   'hard': EC hard/cold reboot;
                   'ap-off': Leave AP off after EC reboot (by default, EC turns
                             AP on after reboot if lid is open).

        Raises:
          error.TestError: If the string of flags is invalid.
        """
        for flag in flags.split():
            if flag not in ('hard', 'ap-off'):
                raise error.TestError(
                        'The flag %s of EC reboot command is invalid.' % flag)
        self.send_command("reboot %s" % flags)


    def set_flash_write_protect(self, enable):
        """Set the software write protect of EC flash.

        Args:
          enable: True to enable write protect, False to disable.
        """
        if enable:
            self.send_command("flashwp enable")
        else:
            self.send_command("flashwp disable")


    def set_hostevent(self, codes):
        """Set the EC hostevent codes.

        Args:
          codes: Hostevent codes, HOSTEVENT_*
        """
        self.send_command("hostevent set %#x" % codes)
        # Allow enough time for EC to process input and set flag.
        # See chromium:371631 for details.
        # FIXME: Stop importing time module if this hack becomes obsolete.
        time.sleep(1)


    def enable_console_channel(self, channel):
        """Find console channel mask and enable that channel only

        @param channel: console channel name
        """
        # The 'chan' command returns a list of console channels,
        # their channel masks and channel numbers
        regexp = r'(\d+)\s+([\w]+)\s+\*?\s+{0}'.format(channel)
        l = self.send_command_get_output('chan', [regexp])
        # Use channel mask and append the 0x for proper hex input value
        cmd = 'chan 0x' + l[0][2]
        # Set console to only output the desired channel
        self.send_command(cmd)


class ChromeUSBPD(ChromeEC):
    """Manages control of a Chrome USBPD.

    We control the Chrome EC via the UART of a Servo board. Chrome USBPD
    provides many interfaces to set and get its behavior via console commands.
    This class is to abstract these interfaces.
    """

    def __init__(self, servo):
        super(ChromeUSBPD, self).__init__(servo, "usbpd_uart")


def ccd_command(func):
    """Decorator for methods only relevant to devices using CCD."""
    @functools.wraps(func)
    def wrapper(instance, *args, **kwargs):
        if instance.using_ccd():
            return func(instance, *args, **kwargs)
        logging.info("not using ccd. ignoring %s", func.func_name)
    return wrapper


class ChromeCr50(ChromeConsole):
    """Manages control of a Chrome Cr50.

    We control the Chrome Cr50 via the console of a Servo board. Chrome Cr50
    provides many interfaces to set and get its behavior via console commands.
    This class is to abstract these interfaces.
    """
    IDLE_COUNT = 'count: (\d+)'
    VERSION_FORMAT = '\d+\.\d+\.\d+'
    VERSION_ERROR = 'Error'
    INACTIVE = '\nRW_(A|B): +(%s|%s)(/DBG|)?' % (VERSION_FORMAT, VERSION_ERROR)
    ACTIVE = '\nRW_(A|B): +\* +(%s)(/DBG|)?' % (VERSION_FORMAT)
    WAKE_CHAR = '\n'


    def __init__(self, servo):
        super(ChromeCr50, self).__init__(servo, "cr50_console")


    def send_command(self, commands):
        """Send command through UART.

        Cr50 will drop characters input to the UART when it resumes from sleep.
        If servo is not using ccd, send some dummy characters before sending the
        real command to make sure cr50 is awake.
        """
        if not self.using_ccd():
            super(ChromeCr50, self).send_command(self.WAKE_CHAR)
        super(ChromeCr50, self).send_command(commands)


    def send_command_get_output(self, command, regexp_list):
        """Send command through UART and wait for response.

        Cr50 will drop characters input to the UART when it resumes from sleep.
        If servo is not using ccd, send some dummy characters before sending the
        real command to make sure cr50 is awake.
        """
        if not self.using_ccd():
            super(ChromeCr50, self).send_command(self.WAKE_CHAR)
        return super(ChromeCr50, self).send_command_get_output(command,
                                                               regexp_list)


    def get_deep_sleep_count(self):
        """Get the deep sleep count from the idle task"""
        result = self.send_command_get_output('idle', [self.IDLE_COUNT])
        return int(result[0][1])


    def clear_deep_sleep_count(self):
        """Clear the deep sleep count"""
        result = self.send_command_get_output('idle c', [self.IDLE_COUNT])
        if int(result[0][1]):
            raise error.TestFail("Could not clear deep sleep count")


    def has_command(self, cmd):
        """Returns 1 if cr50 has the command 0 if it doesn't"""
        try:
            self.send_command_get_output('help', [cmd])
        except:
            logging.info("Image does not include '%s' command", cmd)
            return 0
        return 1


    def erase_nvmem(self):
        """Use flasherase to erase both nvmem sections"""
        if not self.has_command('flasherase'):
            raise error.TestError("need image with 'flasherase'")

        self.send_command('flasherase 0x7d000 0x3000')
        self.send_command('flasherase 0x3d000 0x3000')


    def reboot(self):
        """Reboot Cr50 and wait for CCD to be enabled"""
        self.send_command('reboot')
        self.wait_for_ccd_disable()
        self.ccd_enable()


    def rollback(self):
        """Set the reset counter high enough to force a rollback then reboot"""
        if not self.has_command('rw') or not self.has_command('eraseflashinfo'):
            raise error.TestError("need image with 'rw' and 'eraseflashinfo'")

        # Increase the reset count to above the rollback threshold
        self.send_command('rw 0x40000128 1')
        self.send_command('rw 0x4000012c 15')

        self.send_command('eraseflashinfo')

        self.reboot()


    def get_version_info(self, regexp):
        """Get information from the version command"""
        return self.send_command_get_output('ver', [regexp])[0][1::]


    def get_inactive_version_info(self):
        """Get the active partition, version, and hash"""
        return self.get_version_info(self.INACTIVE)


    def get_active_version_info(self):
        """Get the active partition, version, and hash"""
        return self.get_version_info(self.ACTIVE)


    def using_ccd(self):
        """Returns true if the console is being served using CCD"""
        return 'ccd_cr50' in self._servo.get_servo_version()


    @ccd_command
    def get_ccd_state(self):
        """Get the CCD state from servo

        Returns:
            'off' or 'on' based on whether the cr50 console is working.
        """
        return self._servo.get('ccd_state')


    @ccd_command
    def wait_for_ccd_state(self, state, timeout, raise_error=True):
        """Wait up to timeout seconds for CCD to be 'on' or 'off'
        Args:
            state: a string either 'on' or 'off'.
            timeout: time in seconds to wait
            raise_error: Raise TestFail if the value is state is not reached.

        Raises
            TestFail if ccd never reaches the specified state
        """
        logging.info("Wait until ccd is '%s'", state)
        value = utils.wait_for_value(self.get_ccd_state, state,
                                     timeout_sec=timeout)
        if value != state:
            error_msg = "timed out before detecting ccd '%s'" % state
            if raise_error:
                raise error.TestFail(error_msg)
            logging.warning(error_msg)
        logging.info("ccd is '%s'", value)


    @ccd_command
    def wait_for_ccd_disable(self, timeout=60, raise_error=True):
        """Wait for the cr50 console to stop working"""
        self.wait_for_ccd_state('off', timeout, raise_error)


    @ccd_command
    def wait_for_ccd_enable(self, timeout=60):
        """Wait for the cr50 console to start working"""
        self.wait_for_ccd_state('on', timeout)


    @ccd_command
    def ccd_disable(self):
        """Change the values of the CC lines to disable CCD"""
        logging.info("disable ccd")
        self._servo.set_nocheck('servo_v4_ccd_mode', 'disconnect')
        self.wait_for_ccd_disable()


    @ccd_command
    def ccd_enable(self):
        """Reenable CCD and reset servo interfaces"""
        logging.info("reenable ccd")
        self._servo.set_nocheck('servo_v4_ccd_mode', 'ccd')
        self._servo.set('sbu_mux_enable', 'on')
        self._servo.set_nocheck('power_state', 'ccd_reset')
        self.wait_for_ccd_enable()
