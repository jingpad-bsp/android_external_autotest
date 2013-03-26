# Copyright (c) 2013 The Chromium OS Authors. All rights reserved.
# Use of this source code is governed by a BSD-style license that can be
# found in the LICENSE file.

import time


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

    def power_on(self, rec_mode=REC_ON):
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
                        power on.

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
    def power_on(self, rec_mode=REC_ON):
        self._servo.set_nocheck('rec_mode', rec_mode)
        self._servo.power_short_press()
        if rec_mode == REC_ON:
            time.sleep(self._RECOVERY_INSERT_DELAY)
            self._servo.set('rec_mode', REC_OFF)


_CONTROLLER_BOARD_MAP = {
    'lumpy': _AlexController,
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
