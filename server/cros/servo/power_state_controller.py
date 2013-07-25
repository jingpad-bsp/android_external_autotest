# Copyright (c) 2013 The Chromium OS Authors. All rights reserved.
# Use of this source code is governed by a BSD-style license that can be
# found in the LICENSE file.

import time

from autotest_lib.server.cros.servo import chrome_ec


def _inherit_docstring(cls):
    """Decorator to propagate a docstring to a subclass's method.

    @param cls Class with the method whose docstring is to be
               inherited.  The class must contain a method with
               the same name as the name of the function to be
               decorated.

    """
    def _copy_docstring(methfunc):
        """Actually copy the parent docstring to the child.

        @param methfunc Function that will inherit the docstring.

        """
        methfunc.__doc__ = getattr(cls, methfunc.__name__).__doc__
        return methfunc
    return _copy_docstring


# Constants acceptable to be passed for the `rec_mode` parameter
# to power_on().
#
# REC_ON:  Boot the DUT in recovery mode, i.e. boot from USB or
#   SD card.
# REC_OFF:  Boot in normal mode, i.e. boot from internal storage.

REC_ON = 'on'
REC_OFF = 'off'


class _PowerStateController(object):

    """Class to provide board-specific power operations.

    This class is responsible for "power on" and "power off"
    operations that can operate without making assumptions in
    advance about board state.  It offers an interface that
    abstracts out the different sequences required for different
    board types.

    """

    # Delay in seconds needed between asserting and de-asserting cold
    # or warm reset.  Subclasses will normally override this constant
    # with a board-specific value.
    _RESET_HOLD_TIME = 0.5

    # _EC_RESET_DELAY:  Time required before the EC will be working
    #   after cold reset.  Five seconds is at least twice as long as
    #   necessary for Alex, and is presumably good enough for all other
    #   systems.
    _EC_RESET_DELAY = 5.0

    def __init__(self, servo):
        """Initialize the power state control.

        @param servo Servo object providing the underlying `set` and `get`
                     methods for the target controls.

        """
        self._servo = servo

    def cold_reset(self):
        """Apply cold reset to the DUT.

        This asserts, then de-asserts the 'cold_reset' signal.
        The exact affect on the hardware varies depending on
        the board type.

        """
        self._servo.set_get_all(['cold_reset:on',
                                 'sleep:%.4f' % self._RESET_HOLD_TIME,
                                 'cold_reset:off'])
        # After the reset, give the EC the time it needs to
        # re-initialize.
        time.sleep(self._EC_RESET_DELAY)

    def warm_reset(self):
        """Apply warm reset to the DUT.

        This asserts, then de-asserts the 'warm_reset' signal.
        Generally, this causes the board to restart.

        """
        self._servo.set_get_all(['warm_reset:on',
                                 'sleep:%.4f' % self._RESET_HOLD_TIME,
                                 'warm_reset:off'])

    def recovery_supported(self):
        """Return whether the power on/off methods are supported.

        @return True means the power_on() and power_off() methods will
                not raise a NotImplementedError.  False means they will.

        """
        return False

    def power_off(self):
        """Force the DUT to power off.

        The DUT is guaranteed to be off at the end of this call,
        regardless of its previous state, provided that there is
        working EC and boot firmware.  There is no requirement for
        working OS software.

        """
        raise NotImplementedError()

    def power_on(self, rec_mode=REC_OFF):
        """Force the DUT to power on.

        Prior to calling this function, the DUT must be powered off,
        e.g. with a call to `power_off()`.

        At power on, recovery mode is set as specified by the
        corresponding argument.  When booting with recovery mode on, it
        is the caller's responsibility to unplug/plug in a bootable
        external storage device.

        If the DUT requires a delay after powering on but before
        processing inputs such as USB stick insertion, the delay is
        handled by this method; the caller is not responsible for such
        delays.

        @param rec_mode Setting of recovery mode to be applied at
                        power on. default: REC_OFF aka 'off'

        """
        raise NotImplementedError()


class _AlexController(_PowerStateController):

    """Power-state controller for Alex and compatible boards.

    For Alex, Lumpy, et al., the 'cold_reset' signal forces the unit
    off, and leaves it off.  Recovery mode and developer mode are
    controlled by signals from the Servo board.

    """

    # Time in seconds to allow the firmware to initialize itself and
    # present the "INSERT" screen in recovery mode before actually
    # inserting a USB stick to boot from.
    _RECOVERY_INSERT_DELAY = 10.0

    @_inherit_docstring(_PowerStateController)
    def recovery_supported(self):
        return True

    @_inherit_docstring(_PowerStateController)
    def power_off(self):
        self.cold_reset()

    @_inherit_docstring(_PowerStateController)
    def power_on(self, rec_mode=REC_OFF):
        self._servo.set_nocheck('rec_mode', rec_mode)
        self._servo.power_short_press()
        if rec_mode == REC_ON:
            time.sleep(self._RECOVERY_INSERT_DELAY)
            self._servo.set('rec_mode', REC_OFF)


class _StumpyController(_AlexController):

    """Power-state controller for Stumpy."""

    @_inherit_docstring(_AlexController)
    def power_off(self):
        # In test images in the lab, the 'autoreboot' upstart job will
        # commonly configure the unit so that it reboots after cold
        # reset.  Since we mustn't rely on the OS, we can't know for
        # sure whether the unit will be on or off after cold reset.
        #
        # Fortunately, the autoreboot setting only applies through one
        # reset.  So, after one reset, the unit may be on or off, but
        # autoreboot is disabled.  We can be sure to be off after a
        # second reset as long as it happens before the unit has a
        # chance to run the autoreboot job.
        self.cold_reset()
        self.cold_reset()


class _ParrotController(_PowerStateController):

    """Power-state controller for Parrot.

    On Parrot, uncontrolled assertion of `cold_reset` sometimes
    leaves the DUT unresponsive.  The `cold_reset()` method
    implemented in this class is the only known, reliable way to
    assert the `cold_reset` signal on Parrot.

    The `rec_mode` signal on Parrot is finicky.  These are the
    rules:
     1. You can't read or write the signal unless the DUT is on.
     2. The setting of the signal is only sampled during a cold
        reset.  The sampled setting applies to every boot until the
        next cold reset.
     3. After cold reset, the signal is turned off.
    N.B.  Rule 3 is subtle.  Although `rec_mode` is off after reset,
    because of rule 2, the DUT will continue to boot with the prior
    recovery mode setting until the next cold reset.

    """

    _RESET_HOLD_TIME = 0.0
    _EC_RESET_DELAY = 0.5

    # _PWR_BUTTON_READY_TIME: This represents the time after cold
    #   reset until the EC will be able to see a power button press.
    #   Used in power_off().
    _PWR_BUTTON_READY_TIME = 4

    # _REC_MODE_READY_TIME: This represents the time after power on
    #   until the EC will be able to see changes to rec_mode.  Used
    #   in power_on().
    _REC_MODE_READY_TIME = 0.75

    @_inherit_docstring(_PowerStateController)
    def recovery_supported(self):
        return True

    @_inherit_docstring(_PowerStateController)
    def cold_reset(self):
        # The sequence here leaves the DUT powered on, similar to
        # Chrome EC devices.
        self._servo.set_nocheck('pwr_button', 'press')
        super(_ParrotController, self).cold_reset()
        self._servo.set_nocheck('pwr_button', 'release')

    @_inherit_docstring(_PowerStateController)
    def power_off(self):
        self.cold_reset()
        time.sleep(self._PWR_BUTTON_READY_TIME)
        self._servo.power_short_press()

    @_inherit_docstring(_PowerStateController)
    def power_on(self, rec_mode=REC_OFF):
        self._servo.power_short_press()
        time.sleep(self._REC_MODE_READY_TIME)
        self._servo.set_nocheck('rec_mode', rec_mode)
        self.cold_reset()


class _ChromeECController(_PowerStateController):

    """Power-state controller for systems with a Chrome EC.

    For these systems, after releasing 'cold_reset' the DUT is left
    powered on.  Recovery mode is triggered by simulating keyboard
    recovery by issuing commands to the EC.

    """

    _RESET_HOLD_TIME = 0.1
    _EC_RESET_DELAY = 0.0

    _EC_CONSOLE_DELAY = 1.2

    @_inherit_docstring(_PowerStateController)
    def __init__(self, servo):
        super(_ChromeECController, self).__init__(servo)
        self._ec = chrome_ec.ChromeEC(servo)

    @_inherit_docstring(_PowerStateController)
    def recovery_supported(self):
        return True

    @_inherit_docstring(_PowerStateController)
    def power_off(self):
        self.cold_reset()
        time.sleep(self._EC_CONSOLE_DELAY)
        self._servo.power_long_press()

    @_inherit_docstring(_PowerStateController)
    def power_on(self, rec_mode=REC_OFF):
        if rec_mode == REC_ON:
            # Reset the EC to force it back into RO code; this clears
            # the EC_IN_RW signal, so the system CPU will trust the
            # upcoming recovery mode request.
            self.cold_reset()
            # Restart the EC, but leave the system CPU off...
            self._ec.reboot('ap-off')
            time.sleep(self._EC_CONSOLE_DELAY)
            # ... and tell the EC to tell the CPU we're in recovery mode.
            self._ec.set_hostevent(chrome_ec.HOSTEVENT_KEYBOARD_RECOVERY)
        self._servo.power_short_press()


class _DaisyController(_ChromeECController):
    """Power-state controller for Snow/Daisy systems."""
    _EC_CONSOLE_DELAY = 0.4


class _LinkController(_ChromeECController):

    """Power-state controller for Link.

    Link has a Chrome EC, but the hardware supports the rec_mode
    signal.

    """

    # Time in seconds to allow the BIOS and EC to detect the
    # 'rec_mode' signal after cold reset.
    _RECOVERY_DETECTION_DELAY = 2.5

    @_inherit_docstring(_ChromeECController)
    def power_off(self):
        self._ec.send_command('x86shutdown')

    @_inherit_docstring(_ChromeECController)
    def power_on(self, rec_mode=REC_OFF):
        if rec_mode == REC_ON:
            self._servo.set('rec_mode', REC_ON)
            self.cold_reset()
            time.sleep(self._RECOVERY_DETECTION_DELAY)
            self._servo.set('rec_mode', REC_OFF)
        else:
            self._servo.power_short_press()


_CONTROLLER_BOARD_MAP = {
    'daisy': _DaisyController,
    'spring': _DaisyController,
    'link': _LinkController,
    'lumpy': _AlexController,
    'parrot': _ParrotController,
    'stumpy': _StumpyController,
    'x86-alex': _AlexController
}


def create_controller(servo, board):
    """Create a power state controller instance.

    The controller class will be selected based on the provided
    board type, and instantiated with the provided servo instance.

    @param servo Servo object that will be used to manipulate DUT
                 power states.
    @param board Board name of the DUT to be controlled.

    @returns An instance of a power state controller appropriate to
             the given board type, or `None` if the board is
             unsupported.

    """
    return _CONTROLLER_BOARD_MAP.get(board, _PowerStateController)(servo)
