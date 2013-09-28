# Copyright (c) 2012 The Chromium OS Authors. All rights reserved.
# Use of this source code is governed by a BSD-style license that can be
# found in the LICENSE file.

# TODO(tgao): use XMLHTTP instead of repeated SSH commands. See
#             https://chromium-review.googlesource.com/37180 and the code for
#             remote_pyauto in client/cros for examples

import logging
import os

from autotest_lib.client.common_lib import error

class ScriptNotFound(Exception):
    """Raised when attenuator scripts cannot be found."""

    def __init__(self, script_name):
        """Initialize.

        @param script_name: a string.

        """
        super(ScriptNotFound, self).__init__(
            'Script %s not found in search path' % script_name)


class Attenuator(object):
    """Attenuator support for WiFiTest class.

    This class implements wifi test methods that communicate with a variable
    attenuator over SSH in control network.
    """

    LAB_DOMAIN = '.cros'
    # Host names in RvR test cells.
    HOST1 = 'chromeos1-grover-host1'
    HOST2 = 'chromeos1-grover-host2'
    VALID_HOSTS = [HOST1, HOST2]
    # Look up fixed path loss by AP frequency, host name and port number.
    FREQ_LOSS_MAP = {2437: {HOST1: [44, 44], HOST2: [43, 43]},
                     5220: {HOST1: [49, 46], HOST2: [46, 46]},
                     5765: {HOST1: [49, 47], HOST2: [47, 48]}}
    # We only use 2 ports out of the 4 available.
    PORTS = [0, 1]

    # The scripts that run on the attenuator limit the attenuation to this
    # plus the fixed attenuation for the specific port.
    MAX_VARIABLE_ATTENUATION = 95


    # TODO(tgao): refactor & merge this w/ site_wifitest.install_script()
    def _copy_script(self, script_name, *support_scripts):
        """Copies scripts to DUT.

        @param script_name: a string, main script to copy.
        @param support_scripts: a list of strings, dependent scripts.
        @return a string, script_name if it's copied successfully.

        @raises ScriptNotFound if any source script is not found.

        """
        if script_name in self._installed_scripts:
            return self._installed_scripts[script_name]

        script_dir = self._host.get_tmp_dir()
        script_file = os.path.join(script_dir, script_name)
        for copy_file in [script_name] + list(support_scripts):
            # Look either relative to the current location of this file or
            # relative to ../client/common_lib/cros/site_attenuator/
            # for the script.
            script_relative_paths = [['.'],
                                     ['..', 'client', 'common_lib', 'cros',
                                      'site_attenuator']]
            for rel_path in script_relative_paths:
                src_file = os.path.join(
                    os.path.dirname(os.path.realpath(__file__)),
                    *(rel_path + [copy_file]))
                if os.path.exists(src_file):
                    break
            else:
                raise ScriptNotFound(copy_file)

            dest_file = os.path.join(script_dir,
                                     os.path.basename(src_file))
            self._host.send_file(src_file, dest_file, delete_dest=True)

        self._installed_scripts[script_name] = script_file
        return script_file


    def _run_init_script(self, port, cleanup=False):
        """Initializes attenuator port.

        @param port: an integer, Beaglebone I/O port number (0 or 1).
        @param cleanup: a boolean, True == unexport GPIO pins/reset port.

        """
        # TODO(tgao): bundle these scripts as part of a test image?
        flag = '-c' if cleanup else ''
        self._host.run('python "%s" -p %s %s 2>&1' %
                       (self._init_script, port, flag))


    def _init_ports(self):
        """Initializes attenuator port."""
        for port in self.PORTS:
            self._run_init_script(port)


    def __init__(self, host):
        """Initialize.

        @param host: an Autotest host object, representing the attenuator.

        """
        self._host = host
        self._installed_scripts = dict()
        self.fixed_loss = []  # Fixed path loss on ports 0 and 1 in dB.

        # Install Python scripts on attenuator
        self._init_script = self._copy_script('attenuator_init.py',
                                              'attenuator_util.py',
                                              'constants.py')
        self._config_script = self._copy_script('attenuator_config.py',
                                                'attenuator_util.py',
                                                'constants.py')
        self._init_ports()


    def cleanup(self):
        """Resets attenuator ports."""
        for port in self.PORTS:
            self._run_init_script(port, cleanup=True)


    def get_attenuation(self, port):
        """Reads current attenuation level in dB.

        @param port: an integer, Beaglebone I/O port number (0 or 1).

        """
        self._host.run('python "%s" -p %d 2>&1' % (self._config_script, port))


    def set_variable_attenuation_on_port(self, port, variable_db):
        """Sets desired variable attenuation in dB.

        @param port: port to attenuate.
        @param variable_db: an integer, variable attenuation in dB.

        """
        fixed_db = self.fixed_loss[port]
        total_db = fixed_db + variable_db
        self._host.run('python "%s" -p %d -f %d -t %d 2>&1' %
                       (self._config_script, port, fixed_db, total_db))


    def set_variable_attenuation(self, variable_db):
        """Sets desired variable attenuation in dB.

        @param variable_db: an integer, variable attenuation in dB.

        """
        for port in self.PORTS:
            self.set_variable_attenuation_on_port(port, variable_db)


    def set_total_attenuation_on_port(self, port, total_db):
        """Sets desired total attenuation in dB.

        @param port: port to attenuate.
        @param total_db: an integer, total attenuation in dB.

        """
        self._host.run('python "%s" -p %d -f %d -t %d 2>&1' %
                       (self._config_script, port, self.fixed_loss[port],
                        total_db))


    def set_total_attenuation(self, total_db):
        """Sets desired total attenuation in dB.

        @param total_db: an integer, total attenuation in dB.

        """
        for port in self.PORTS:
            self.set_total_attenuation_on_port(port, total_db)


    @staticmethod
    def _approximate_frequency(freq):
        """Finds an approximate frequency to freq.

        In case freq is not present in FREQ_LOSS_MAP, we use a value
        from a nearby channel as an approximation.

        @param freq an integer, frequency in MHz.
        @returns an integer, approximate frequency from FREQ_LOSS_MAP.

        """
        old_offset = None
        approx_freq = None
        for f in sorted(Attenuator.FREQ_LOSS_MAP.keys()):
            new_offset = abs(f - freq)
            if old_offset is not None and new_offset > old_offset:
                break
            old_offset = new_offset
            approx_freq = f

        logging.info('Approximating attenuation for frequency %d with '
                     'constants for frequency %d.', freq, approx_freq)
        return approx_freq


    def config(self, hostname, freq):
        """Configures variable attenuator for a given frequency.

        @param hostname a string, DUT host name.
        @param freq an integer, frequency in MHz.
        @raises TestError if DUT hostname is unexpected.

        """
        if hostname.endswith(self.LAB_DOMAIN):
            hostname = hostname[:-len(self.LAB_DOMAIN)]
        if hostname not in self.VALID_HOSTS:
            raise error.TestError('Unexpected RvR host name %r.' % hostname)

        # Look up path loss by frequency. Approximate if needed.
        freq_used = freq
        if freq not in self.FREQ_LOSS_MAP:
            freq_used = self._approximate_frequency(freq)
        logging.info('Looking up fixed path loss on freq %d', freq_used)

        self.fixed_loss = self.FREQ_LOSS_MAP[freq_used][hostname]
        self.set_variable_attenuation(0)


