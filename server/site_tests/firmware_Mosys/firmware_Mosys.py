# Copyright (c) 2014 The Chromium OS Authors. All rights reserved.
# Use of this source code is governed by a BSD-style license that can be
# found in the LICENSE file.

import logging
import re

from autotest_lib.client.common_lib import error
from autotest_lib.client.common_lib import utils
from autotest_lib.server.cros.faft.firmware_test import FirmwareTest


class firmware_Mosys(FirmwareTest):
    """
    Mosys commands test for Firmware values.

    Execute
    a. mosys -k smbios info bios
    b. mosys -k ec info
    c. mosys platform name
    d. mosys eeprom map
    e. mosys platform vendor

    """
    version = 1


    def initialize(self, host, cmdline_args, dev_mode=False):
        # Parse arguments from command line
        dict_args = utils.args_to_dict(cmdline_args)
        super(firmware_Mosys, self).initialize(host, cmdline_args)
        self.setup_dev_mode(dev_mode)

    def run_cmd(self, command):
        """
        Log and execute command and return the output.

        @param command: Command to executeon device.
        @returns the output of command.

        """
        logging.info('Execute %s', command)
        output = self.faft_client.system.run_shell_command_get_output(command)
        logging.info('Output %s', output)
        return output

    def check_ec_version(self, exp_ec_version):
        """
        Compare output of 'ectool version' for the current firmware
        copy to exp_ec_version.

        @param exp_ec_version: The exepected EC version string.
        @returns True if EC version string match expected.
        @raises error.TestError if failed to locate pattern.

        """
        lines = self.run_cmd('ectool version')
        fwcopy_pattern = re.compile('Firmware copy: (.*)$')
        ver_pattern = re.compile('(R[OW]) version:    (.*)$')
        version = {}
        for line in lines:
            ver_matched = ver_pattern.match(line)
            if ver_matched:
                version[ver_matched.group(1)] = ver_matched.group(2)
            fwcopy_matched = fwcopy_pattern.match(line)
            if fwcopy_matched:
                fwcopy = fwcopy_matched.group(1)
        try:
            actual_version = version[fwcopy]
        except:
            raise error.TestError('Failed to locate version from ectool:\n%s' %
                                  '\n'.join(lines))
        logging.info('Expected ec version %s actual_version %s',
                     exp_ec_version, actual_version)
        return exp_ec_version == actual_version

    def check_lsb_info(self, fieldname, exp_value):
        """
        Comapre output of fieldname in /etc/lsb-release to exp_value.

        @param fieldname: field name in lsd-release file.
        @param exp_value: expected value for fieldname
        @returns True if exp_value is the same as value in lsb-release file.
        @raises error.TestError if failed to locate pattern.

        """
        command = 'cat /etc/lsb-release'
        lines = self.run_cmd(command)
        pattern = re.compile(fieldname + '=(.*)$')
        for line in lines:
            matched = pattern.match(line)
            if matched:
                actual = matched.group(1)
                logging.info('Expected %s %s actual %s',
                             fieldname, exp_value, actual)
                return exp_value.lower() == actual.lower()
        raise error.TestError('Failed to locate field %s from %s\n%s' %
                              fieldname, command, '\n'.join(lines))

    def run_once(self, dev_mode=False):
        # Test case: Mosys Commands
        # a. mosys -k smbios info bios
        command = 'mosys -k smbios info bios'
        output = self.run_cmd(command)[0]
        p = re.compile('vendor="coreboot" version="(.*)"'
                       ' release_date="[/0-9]+" size="[0-9]+ KB"')
        v = p.match(output)
        if not v:
          raise error.TestFail('execute %s failed' % command)
        version = v.group(1)
        self.check_state((self.checkers.crossystem_checker, {'fwid': version}))

        # b. mosys -k ec info
        command = 'mosys -k ec info'
        output = self.run_cmd(command)[0]
        p = re.compile('vendor="[a-z]+" name="[ -~]+" fw_version="(.*)"')
        v = p.match(output)
        if not v:
          raise error.TestFail('execute %s failed' % command)
        version = v.group(1)
        self.check_state((self.check_ec_version, version))

        # c. mosys platform name
        output = self.run_cmd('mosys platform name')[0]
        self.check_state((self.check_lsb_info, ('CHROMEOS_RELEASE_BOARD',
                                                output)))

        # d. mosys eeprom map
        command = 'mosys eeprom map'
        lines = self.run_cmd(command)
        for line in lines:
            row = line.split(' | ')
            if(row[1] in ['RW_SECTION_A', 'RW_SECTION_B'] and
               '0x00000000' in row[2:3]):
                raise error.TestFail('zero located in %s', line)

        # e. mosys platform vendor
        # Output will be GOOGLE until launch, see crosbug/p/29755
        command = 'mosys platform vendor'
        output = self.run_cmd(command)[0]
        p = re.compile('^\w+$')
        if not p.match(output):
            raise error.TestFail('output is not a string Expect GOOGLE'
                                 ' or name of maker.')
