# Copyright (c) 2014 The Chromium OS Authors. All rights reserved.
# Use of this source code is governed by a BSD-style license that can be
# found in the LICENSE file.

import logging

from autotest_lib.client.common_lib import error
from autotest_lib.server.cros.network import attenuator


# This map represents the fixed loss overhead on a given antenna line.
# The map maps from:
#     attenuator hostname -> attenuator number -> frequency -> loss in dB.
HOST_TO_FIXED_ATTENUATIONS = {
        'chromeos15-row3-rack9-host1-attenuator': {
                0: {2437: 59, 5220: 59, 5765: 59},
                1: {2437: 52, 5220: 54, 5765: 54},
                2: {2437: 59, 5220: 59, 5765: 59},
                3: {2437: 52, 5220: 54, 5765: 54}},
        'chromeos15-row3-rack9-host2-attenuator': {
                0: {2437: 64, 5220: 62, 5765: 62},
                1: {2437: 58, 5220: 57, 5765: 57},
                2: {2437: 64, 5220: 62, 5765: 62},
                3: {2437: 58, 5220: 57, 5765: 57}},
        'chromeos15-row3-rack9-host3-attenuator': {
                0: {2437: 60, 5220: 58, 5765: 58},
                1: {2437: 52, 5220: 57, 5765: 57},
                2: {2437: 60, 5220: 58, 5765: 58},
                3: {2437: 52, 5220: 57, 5765: 57}},
        'chromeos15-row3-rack9-host4-attenuator': {
                0: {2437: 52, 5220: 58, 5765: 58},
                1: {2437: 59, 5220: 60, 5765: 60},
                2: {2437: 52, 5220: 58, 5765: 58},
                3: {2437: 59, 5220: 60, 5765: 60}},
        'chromeos15-row3-rack9-host5-attenuator': {
                0: {2437: 58, 5220: 60, 5765: 60},
                1: {2437: 53, 5220: 58, 5765: 58},
                2: {2437: 58, 5220: 60, 5765: 60},
                3: {2437: 53, 5220: 58, 5765: 58}},
        'chromeos15-row3-rack9-host6-attenuator': {
                0: {2437: 61, 5220: 62, 5765: 62},
                1: {2437: 53, 5220: 60, 5765: 60},
                2: {2437: 61, 5220: 62, 5765: 62},
                3: {2437: 53, 5220: 60, 5765: 60}},
        'chromeos15-row3-rack10-host1-attenuator': {
                0: {2437: 53, 5220: 56, 5765: 56},
                1: {2437: 52, 5220: 56, 5765: 56},
                2: {2437: 53, 5220: 56, 5765: 56},
                3: {2437: 52, 5220: 56, 5765: 56}},
        'chromeos15-row3-rack10-host2-attenuator': {
                0: {2437: 59, 5220: 59, 5765: 59},
                1: {2437: 59, 5220: 60, 5765: 60},
                2: {2437: 59, 5220: 59, 5765: 59},
                3: {2437: 59, 5220: 60, 5765: 60}},
        'chromeos15-row3-rack10-host3-attenuator': {
                0: {2437: 52, 5220: 56, 5765: 56},
                1: {2437: 64, 5220: 63, 5765: 63},
                2: {2437: 52, 5220: 56, 5765: 56},
                3: {2437: 64, 5220: 63, 5765: 63}},
        'chromeos15-row3-rack10-host4-attenuator': {
                0: {2437: 52, 5220: 55, 5765: 55},
                1: {2437: 58, 5220: 58, 5765: 58},
                2: {2437: 52, 5220: 55, 5765: 55},
                3: {2437: 58, 5220: 58, 5765: 58}},
        'chromeos15-row3-rack10-host5-attenuator': {
                0: {2437: 57, 5220: 58, 5765: 58},
                1: {2437: 52, 5220: 55, 5765: 55},
                2: {2437: 57, 5220: 58, 5765: 58},
                3: {2437: 52, 5220: 55, 5765: 55}},
        'chromeos15-row3-rack10-host6-attenuator': {
                0: {2437: 57, 5220: 57, 5765: 57},
                1: {2437: 52, 5220: 55, 5765: 55},
                2: {2437: 57, 5220: 57, 5765: 57},
                3: {2437: 52, 5220: 55, 5765: 55}},
        }


class AttenuatorController(object):
    """Represents a minicircuits variable attenuator.

    This device is used to vary the attenuation between a router and a client.
    This allows us to measure throughput as a function of signal strength and
    test some roaming situations.  The throughput vs signal strength tests
    are referred to rate vs range (RvR) tests in places.

    """

    @property
    def supported_attenuators(self):
        """@return iterable of int attenuators supported on this host."""
        return self._fixed_attenuations.keys()


    def __init__(self, hostname):
        """Construct a AttenuatorController.

        @param hostname: Hostname representing minicircuits attenuator.

        """
        super(AttenuatorController, self).__init__()
        if hostname not in HOST_TO_FIXED_ATTENUATIONS.keys():
            raise error.TestError('Unexpected RvR host name %r.' % hostname)
        self._fixed_attenuations = HOST_TO_FIXED_ATTENUATIONS[hostname]
        num_atten = len(self.supported_attenuators)

        self._attenuator = attenuator.Attenuator(hostname, num_atten)
        self.set_variable_attenuation(0)


    def _approximate_frequency(self, attenuator_num, freq):
        """Finds an approximate frequency to freq.

        In case freq is not present in self._fixed_attenuations, we use a value
        from a nearby channel as an approximation.

        @param attenuator_num: attenuator in question on the remote host.  Each
                attenuator has a different fixed path loss per frequency.
        @param freq: int frequency in MHz.
        @returns int approximate frequency from self._fixed_attenuations.

        """
        old_offset = None
        approx_freq = None
        for defined_freq in self._fixed_attenuations[attenuator_num].keys():
            new_offset = abs(defined_freq - freq)
            if old_offset is None or new_offset < old_offset:
                old_offset = new_offset
                approx_freq = defined_freq

        logging.debug('Approximating attenuation for frequency %d with '
                      'constants for frequency %d.', freq, approx_freq)
        return approx_freq


    def close(self):
        """Close variable attenuator connection."""
        self._attenuator.close()


    def set_total_attenuation(self, atten_db, frequency_mhz,
                              attenuator_num=None):
        """Set the total attenuation on one or all attenuators.

        @param atten_db: int level of attenuation in dB.  This must be
                higher than the fixed attenuation level of the affected
                attenuators.
        @param frequency_mhz: int frequency for which to calculate the
                total attenuation.  The fixed component of attenuation
                varies with frequency.
        @param attenuator_num: int attenuator to change, or None to
                set all variable attenuators.

        """
        affected_attenuators = self.supported_attenuators
        if attenuator_num is not None:
            affected_attenuators = [attenuator_num]
        for atten in affected_attenuators:
            freq_to_fixed_loss = self._fixed_attenuations[atten]
            approx_freq = self._approximate_frequency(atten,
                                                      frequency_mhz)
            variable_atten_db = atten_db - freq_to_fixed_loss[approx_freq]
            self.set_variable_attenuation(variable_atten_db,
                                          attenuator_num=atten)


    def set_variable_attenuation(self, atten_db, attenuator_num=None):
        """Set the variable attenuation on one or all attenuators.

        @param atten_db: int non-negative level of attenuation in dB.
        @param attenuator_num: int attenuator to change, or None to
                set all variable attenuators.

        """

        affected_attenuators = self.supported_attenuators
        if attenuator_num is not None:
            affected_attenuators = [attenuator_num]
        for atten in affected_attenuators:
            self._attenuator.set_atten(atten, atten_db)
            if int(self._attenuator.get_atten(atten)) != atten_db:
                raise error.TestError('Attenuation did not set as expected on '
                                      'attenuator %d' % atten)
            logging.info('%ddb attenuation set successfully on attenautor %d',
                         atten_db, atten)


    def get_minimal_total_attenuation(self):
        """Get attenuator's maximum fixed attenuation value.

        This is pulled from the current attenuator's lines and becomes the
        minimal total attenuation when stepping through attenuation levels.

        @return maximum starting attenuation value

        """
        max_atten = 0
        for atten_num in self._fixed_attenuations.iterkeys():
            atten_values = self._fixed_attenuations[atten_num].values()
            max_atten = max(max(atten_values), max_atten)
        return max_atten
