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
                # Some board will have prefix.  Example nyan_big for big.
                return exp_value.lower() in actual.lower()
        raise error.TestError('Failed to locate field %s from %s\n%s' %
                              fieldname, command, '\n'.join(lines))

    def run_once(self, dev_mode=False):
        # Get a list of available mosys commands.
        command = 'mosys help'
        lines = self.run_cmd(command)[0]
        command_list = []
        cmdlist_start = False
        for line in lines:
            if cmdlist_start:
                cmdlst = re.split('\s+', line)
                if len(cmdlst) > 2:
                    command_list.append(cmdlst[1])
            elif 'Commands:' in line:
                cmdlist_start = True

        # Test case: Mosys Commands
        # a. mosys -k smbios info bios
        if 'smbios' in command_list:
            command = 'mosys -k smbios info bios'
            output = self.run_cmd(command)[0]
            p = re.compile('vendor="coreboot" version="(.*)"'
                           ' release_date="[/0-9]+" size="[0-9]+ KB"')
            v = p.match(output)
            if not v:
              raise error.TestFail('execute %s failed' % command)
            version = v.group(1)
            self.check_state((self.checkers.crossystem_checker,
                             {'fwid': version}))

        # b. mosys -k ec info
        if self.faft_config.chrome_ec:
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
        command = "mosys eeprom map|egrep 'RW_SHARED|RW_SECTION_[AB]'"
        lines = self.run_cmd(command)
        if len(lines) != 3:
            raise error.TestFail('Expect RW_SHARED|RW_SECTION_[AB] got "%s"' % lines)
        emap = {'RW_SECTION_A': 0, 'RW_SECTION_B': 0, 'RW_SHARED': 0}
        for line in lines:
            row = line.split(' | ')
            if row[1] in emap:
                emap[row[1]] += 1
            if row[2] == '0x00000000':
                raise error.TestFail('Expect non zero but got %s instead(%s)' %
                                     (row[2], line))
            if row[3] == '0x00000000':
                raise error.TestFail('Expect non zero but got %s instead(%s)' %
                                     (row[3], line))
        # Check that there are one A and one B.
        if emap['RW_SECTION_A'] != 1 or emap['RW_SECTION_B'] != 1:
            raise error.TestFail('Missing RW_SECTION A or B, %s' % lines)

        # e. mosys platform vendor
        # Output will be GOOGLE until launch, see crosbug/p/29755
        command = 'mosys platform vendor'
        output = self.run_cmd(command)[0]
        p = re.compile('^[-\w\s]+$')
        if not p.match(output):
            raise error.TestFail('output is not a string Expect GOOGLE'
                                 ' or name of maker.')
