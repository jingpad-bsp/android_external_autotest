# Copyright (c) 2013 The Chromium OS Authors. All rights reserved.
# Use of this source code is governed by a BSD-style license that can be
# found in the LICENSE file.

import time


class _PowerStateController(object):

    """Class to provide board-specific power operations.

    This class is responsible for "power on" and "power off"
    operations that can operate without making assumptions in
    advance about board state.  It offers an interface that
    abstracts out the different sequences required for different
    board types.

    """

    DEV_ON = 'on'
    DEV_OFF = 'off'

    REC_ON = 'on'
    REC_OFF = 'off'

    def __init__(self, servo):
        """Initialize the power state control.

        @param servo Servo object providing the underlying `set` and `get`
                     methods for the target controls.

        """
        self._servo = servo

    def power_off(self):
        """Force the DUT to power off.

        The device is guaranteed to be off at the end of this call,
        regardless of its previous state, provided that there is
        working EC and boot firmware.  There is no requirement for
        working OS software.

        """
        raise NotImplementedError()

    def power_on(self, dev_mode=DEV_OFF, rec_mode=REC_ON):
        """Force the DUT to power on.

        At power on, recovery mode and dev mode are set as specified
        by the corresponding arguments.

        Prior to calling this function, the DUT must be powered off,
        e.g. with a call to `power_off()`.

        @param dev_mode Setting of dev mode to be applied at power on.
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

    # _REC_MODE_DETECTION_DELAY:  Time in seconds to leave the
    #   recovery button pressed after power on, in order to allow
    #   the BIOS to detect the button state.
    _REC_MODE_DETECTION_DELAY = 0.5

    # Time required for the EC to be working after cold reset.
    # Five seconds is at least twice as big as necessary for Alex,
    # and is presumably good enough for all future systems.
    _EC_RESET_DELAY = 5.0

    def power_off(self):
        """Force the DUT to power off.

        The device is guaranteed to be off at the end of this call,
        regardless of its previous state, provided that there is
        working EC and boot firmware.  There is no requirement for
        working OS software.

        """
        self._servo.cold_reset()

    def power_on(self, dev_mode=_PowerStateController.DEV_OFF,
                       rec_mode=_PowerStateController.REC_ON):
        """Force the DUT to power on.

        At power on, recovery mode and dev mode are set as specified
        by the corresponding arguments.

        Prior to calling this function, the DUT must be powered off,
        e.g. with a call to `power_off()`.

        @param dev_mode Setting of dev mode to be applied at power on.
        @param rec_mode Setting of recovery mode to be applied at
                        power on.

        """
        try:
            self._servo.set_nocheck('dev_mode', dev_mode)
            self._servo.set_nocheck('rec_mode', rec_mode)
            self._servo.power_short_press()
            if rec_mode == self.REC_ON:
                time.sleep(self._REC_MODE_DETECTION_DELAY)
                self._servo.set('rec_mode', self.REC_OFF)
        except:
            # If anything went wrong, try to put things back as they
            # were.  This is best-effort only; callers shouldn't
            # assume this worked...
            self.power_off()
            raise


_CONTROLLER_BOARD_MAP = {
    'x86-alex': _AlexController,
    'lumpy': _AlexController
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
    board_class = _CONTROLLER_BOARD_MAP.get(board)
    if not board_class:
        return None
    return board_class(servo)
