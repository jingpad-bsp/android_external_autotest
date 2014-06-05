# Copyright (c) 2013 The Chromium OS Authors. All rights reserved.
# Use of this source code is governed by a BSD-style license that can be
# found in the LICENSE file.


class _PowerStateController(object):

    """Class to provide board-specific power operations.

    This class is responsible for "power on" and "power off"
    operations that can operate without making assumptions in
    advance about board state.  It offers an interface that
    abstracts out the different sequences required for different
    board types.

    """

    # Constants acceptable to be passed for the `rec_mode` parameter
    # to power_on().
    #
    # REC_ON:  Boot the DUT in recovery mode, i.e. boot from USB or
    #   SD card.
    # REC_OFF:  Boot in normal mode, i.e. boot from internal storage.

    REC_ON = 'rec'
    REC_OFF = 'on'

    # Delay in seconds needed between asserting and de-asserting
    # warm reset.
    _RESET_HOLD_TIME = 0.5

    def __init__(self, servo):
        """Initialize the power state control.

        @param servo Servo object providing the underlying `set` and `get`
                     methods for the target controls.

        """
        self._servo = servo

    def reset(self):
        """Force the DUT to reset.

        The DUT is guaranteed to be on at the end of this call,
        regardless of its previous state, provided that there is
        working OS software. This also guarantees that the EC has
        been restarted.

        """
        self._servo.set_nocheck('power_state', 'reset')

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
        return True

    def power_off(self):
        """Force the DUT to power off.

        The DUT is guaranteed to be off at the end of this call,
        regardless of its previous state, provided that there is
        working EC and boot firmware.  There is no requirement for
        working OS software.

        """
        self._servo.set_nocheck('power_state', 'off')

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
        self._servo.set_nocheck('power_state', rec_mode)


def create_controller(servo):
    """Create a power state controller instance.

    @param servo Servo object that will be used to manipulate DUT
                 power states.

    @returns An instance of _PowerStateController for the servo
             object.

    """
    return _PowerStateController(servo)
