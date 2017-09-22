# Copyright 2017 The Chromium OS Authors. All rights reserved.
# Use of this source code is governed by a BSD-style license that can be
# found in the LICENSE file.

import functools
import logging
import time

from autotest_lib.client.bin import utils
from autotest_lib.client.common_lib import error
from autotest_lib.client.common_lib.cros import cr50_utils
from autotest_lib.server.cros.servo import chrome_ec


def ccd_command(func):
    """Decorator for methods only relevant to devices using CCD."""
    @functools.wraps(func)
    def wrapper(instance, *args, **kwargs):
        """Ignore ccd functions if we aren't using ccd"""
        if instance.using_ccd():
            return func(instance, *args, **kwargs)
        logging.info("not using ccd. ignoring %s", func.func_name)
    return wrapper


class ChromeCr50(chrome_ec.ChromeConsole):
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
    BID_FORMAT = ':\s+([a-f0-9:]+) '
    # The first group in the version strings is the relevant partition. Match
    # that to get the relevant board id
    ACTIVE_BID = r'%s.*\1%s' % (ACTIVE, BID_FORMAT)
    INACTIVE_BID = r'%s.*\1%s' % (INACTIVE, BID_FORMAT)
    WAKE_CHAR = '\n'
    START_UNLOCK_TIMEOUT = 20
    GETTIME = ['= (\S+)']
    UNLOCK = ['Unlock sequence starting. Continue until (\S+)']
    FWMP_LOCKED_PROD = ["Managed device console can't be unlocked"]
    FWMP_LOCKED_DBG = ['Ignoring FWMP unlock setting']
    MAX_RETRY_COUNT = 5
    START_STR = ['(.*Console is enabled;)']


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
        """Reboot Cr50 and wait for cr50 to reset"""
        response = [] if self.using_ccd() else self.START_STR
        self.send_command_get_output('reboot', response)

        # ccd will stop working after the reboot. Wait until that happens and
        # reenable it.
        if self.using_ccd():
            self.wait_for_reboot()


    def _uart_wait_for_reboot(self, timeout=60):
        """Wait for the cr50 to reboot and enable the console.

        This will wait up to timeout seconds for cr50 to print the start string.

        Args:
            timeout: seconds to wait to detect the reboot.
        """
        original_timeout = float(self._servo.get('cr50_console_timeout'))
        # Change the console timeout to timeout, so we wait at least that long
        # for cr50 to print the start string.
        self._servo.set_nocheck('cr50_console_timeout', timeout)
        try:
            self.send_command_get_output('\n', self.START_STR)
            logging.info('Detected cr50 reboot')
        except error.TestFail, e:
            logging.info('Failed to detect cr50 reboot')
        # Reset the timeout.
        self._servo.set_nocheck('cr50_console_timeout', original_timeout)


    def wait_for_reboot(self, timeout=60):
        """Wait for cr50 to reboot"""
        if self.using_ccd():
            # Cr50 USB is reset when it reboots. Wait for the CCD connection to
            # go down to detect the reboot.
            self.wait_for_ccd_disable(timeout, raise_error=False)
            self.ccd_enable()
        else:
            self._uart_wait_for_reboot(timeout)


    def rollback(self, eraseflashinfo=True, chip_bid=None, chip_flags=None):
        """Set the reset counter high enough to force a rollback then reboot

        Set the new board id before rolling back if one is given.

        Args:
            eraseflashinfo: True if eraseflashinfo should be run before rollback
            chip_bid: the integer representation of chip board id or None if the
                      board id should be erased during rollback
            chip_flags: the integer representation of chip board id flags or
                        None if the board id should be erased during rollback
        """
        if not self.has_command('rw') or not self.has_command('eraseflashinfo'):
            raise error.TestError("need image with 'rw' and 'eraseflashinfo'")

        inactive_partition = self.get_inactive_version_info()[0]
        # Increase the reset count to above the rollback threshold
        self.send_command('rw 0x40000128 1')
        self.send_command('rw 0x4000012c %d' % (self.MAX_RETRY_COUNT + 2))

        # Set the board id if both the board id and flags have been given.
        set_bid = chip_bid and chip_flags

        # Erase the infomap
        if eraseflashinfo or set_bid:
            self.send_command('eraseflashinfo')

        # Update the board id after it has been erased
        if set_bid:
            self.send_command('bid 0x%x 0x%x' % (chip_bid, chip_flags))

        self.reboot()

        running_partition = self.get_active_version_info()[0]
        if inactive_partition != running_partition:
            raise error.TestError("Failed to rollback to inactive image")


    def rolledback(self):
        """Returns true if cr50 just rolled back"""
        return int(self._servo.get('cr50_reset_count')) > self.MAX_RETRY_COUNT


    def get_version_info(self, regexp):
        """Get information from the version command"""
        return self.send_command_get_output('ver', [regexp])[0][1::]


    def get_inactive_version_info(self):
        """Get the active partition, version, and hash"""
        return self.get_version_info(self.INACTIVE)


    def get_active_version_info(self):
        """Get the active partition, version, and hash"""
        return self.get_version_info(self.ACTIVE)


    def get_active_board_id_str(self):
        """Get the running image board id.

        Returns:
            The board id string or None if the image does not support board id
            or the image is not board id locked.
        """
        # Getting the board id from the version console command is only
        # supported in board id locked images .22 and above. Any image that is
        # board id locked will have support for getting the image board id.
        #
        # If board id is not supported on the device, return None. This is
        # still expected on all current non board id locked release images.
        #
        # TODO(mruthven): switch to only trying once when getting the cr50
        # console command output becomes entirely reliable.
        for i in range(3):
            try:
                version_info = self.get_version_info(self.ACTIVE_BID)
                break
            except error.TestFail, e:
                logging.info(e.message)
                version_info = None

        if not version_info:
            logging.info('Cannot use the version to get the board id')
            return None

        bid = version_info[3]
        logging.info('%r %r', version_info, bid)

        return bid if bid != cr50_utils.EMPTY_IMAGE_BID else None


    def get_version(self):
        """Get the RW version"""
        return self.get_active_version_info()[1].strip()


    def using_servo_v4(self):
        """Returns true if the console is being served using servo v4"""
        return 'servo_v4' in self._servo.get_servo_version()


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


    def ccd_disable(self):
        """Change the values of the CC lines to disable CCD"""
        if self.using_servo_v4():
            logging.info("disable ccd")
            self._servo.set_nocheck('servo_v4_dts_mode', 'off')
            self.wait_for_ccd_disable()


    @ccd_command
    def ccd_enable(self):
        """Reenable CCD and reset servo interfaces"""
        logging.info("reenable ccd")
        self._servo.set_nocheck('servo_v4_dts_mode', 'on')
        self._servo.set_nocheck('power_state', 'ccd_reset')
        self.wait_for_ccd_enable()


    def _level_change_req_pp(self, level):
        """Returns True if setting the level will require physical presence"""
        testlab_pp = level != 'testlab open' and 'testlab' in level
        open_pp = level == 'open'
        return testlab_pp or open_pp


    def ccd_set_level(self, level):
        """Increase the console timeout and try disabling the lock."""
        # TODO(mruthven): add support for CCD password
        level = level.lower().strip()

        if level in self._servo.get('cr50_ccd_level').lower():
            logging.info('CCD privilege level is already %s', level)
            return

        if 'testlab' in level:
            raise error.TestError("Can't change testlab mode using "
                "ccd_set_level")

        testlab_enabled = self._servo.get('cr50_testlab') == 'enabled'
        req_pp = self._level_change_req_pp(level)
        has_pp = not self.using_ccd()
        dbg_en = 'DBG' in self._servo.get('cr50_version')

        if req_pp and not has_pp:
            raise error.TestError("Can't change privilege level to '%s' "
                "without physical presence." % level)

        if not testlab_enabled and not has_pp:
            raise error.TestError("Wont change privilege level without "
                "physical presence or testlab mode enabled")

        resp = ['(Access Denied|%sCCD %s)' % ('Starting ' if req_pp else '',
                                              level)]
        # Start the unlock process.
        rv = self.send_command_get_output('ccd %s' % level, resp)
        if 'Access Denied' in rv[0][1]:
            raise error.TestFail("'ccd %s' Access Denied" % level)

        if req_pp:
            # DBG images have shorter unlock processes
            unlock_timeout = 15 if dbg_en else 300
            end_time = time.time() + unlock_timeout

            logging.info('Pressing power button for %ds to unlock the console.',
                         unlock_timeout)
            logging.info('The process should end at %s', time.ctime(end_time))

            # Press the power button once a second to unlock the console.
            while time.time() < end_time:
                self._servo.power_short_press()
                time.sleep(1)

        if level not in self._servo.get('cr50_ccd_level').lower():
            raise error.TestFail('Could not set privilege level to %s' % level)

        logging.info('Successfully set CCD privelege level to %s', level)


    def gettime(self):
        """Get the current cr50 system time"""
        result = self.send_command_get_output('gettime', [' = (.*) s'])
        return float(result[0][1])


    def wait_until_update_is_allowed(self):
        """Wait until cr50 will be able to accept an update.

        Cr50 rejects any attempt to update if it has been less than 60 seconds
        since it last recovered from deep sleep or came up from reboot. This
        will wait until cr50 gettime shows a time greater than 60.
        """
        cr50_time = self.gettime()
        if cr50_time < 60:
            sleep_time = 61 - cr50_time
            logging.info('Cr50 has been up for %ds waiting %ds before update',
                         cr50_time, sleep_time)
            time.sleep(sleep_time)
