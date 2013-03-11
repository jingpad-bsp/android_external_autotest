# Copyright (c) 2013 The Chromium OS Authors. All rights reserved.
# Use of this source code is governed by a BSD-style license that can be
# found in the LICENSE file.

import logging
import time


class PowerStateController(object):

    """Class to provide board-specific power operations.

    This class is responsible for "power on" and "power off"
    operations that can operate without making assumptions in
    advance about board state.  It offers an interface that
    abstracts out the different sequences required for different
    board types.

    TODO(jrbarnette):  This class is intended to be and abstract
    superclass enabling support for multiple board types.
    Currently, this class effectively hard-codes support for
    x86-alex and lumpy only.

    """

    # _REC_MODE_DETECTION_DELAY:  Time in seconds to leave the
    #   recovery button pressed after power on, in order to allow
    #   the BIOS to detect the button state.
    _REC_MODE_DETECTION_DELAY = 0.5

    # Time required for the EC to be working after cold reset.
    # Five seconds is at least twice as big as necessary for Alex,
    # and is presumably good enough for all future systems.
    _EC_RESET_DELAY = 5.0

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
        self._servo.cold_reset()

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
        try:
            self._servo.set_nocheck('dev_mode', dev_mode)
            self._servo.set_nocheck('rec_mode', rec_mode)
            self._servo.power_short_press()
            if rec_mode == self.REC_ON:
                time.sleep(self._REC_MODE_DETECTION_DELAY)
                self._servo.set('rec_mode', self.REC_OFF)
        except:
            # In case anything went wrong we want to make sure to do a clean
            # reset.
            self._servo.set_nocheck('rec_mode', self.REC_OFF)
            self._servo.warm_reset()
            raise
