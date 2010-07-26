# Copyright (c) 2010 The Chromium OS Authors. All rights reserved.
# Use of this source code is governed by a BSD-style license that can be
# found in the LICENSE file.

import os

from autotest_lib.client.bin import test, utils
from autotest_lib.client.common_lib import error
from autotest_lib.client.common_lib import flashrom_util


class factory_EnableWriteProtect(test.test):
    """
    Factory test for enable EEPROM Write Protection

    WARNING: THE RO SECTIONS OF YOUR FLASHROM WILL BECOME READONLY
             AFTER RUNNING THIS TEST.
    NOTE: This test only enables write protection. If you want to check
          if the protection stuff is set correctly, use test
          hardware_EepromWriteProtect instead.
    """
    version = 1
    verbose = True

    def setup(self):
        """ autotest setup procedure """
        self.flashrom = flashrom_util.flashrom_util(verbose=self.verbose)

    def run_once(self):
        """ core testing procedure """
        # The EEPROM should be programmed as:
        #     (BIOS)  LSB [ RW | RO ] MSB
        #     (EC)    LSB [ RO | RW ] MSB
        # Each part of RW/RO section occupies half of the EEPROM.
        eeprom_sets = (
            { # BIOS
                'name': 'BIOS',
                'layout': 'rw|ro',
                'target': 'bios',
            }, { # Embedded Controller
                'name': 'EC',
                'layout': 'ro|rw',
                'target': 'ec',
            }, )

        # always restore system flashrom selection to this one
        system_default_selection = 'bios'

        for conf in eeprom_sets:
            # select target
            if not self.flashrom.select_target(conf['target']):
                raise error.TestError('ERROR: cannot select target %s' %
                        conf['name'])

            # build layout
            original = self.flashrom.read_whole()
            if not original:
                raise error.TestError('Cannot read valid flash rom data.')
            flashrom_size = len(original)
            layout = self.flashrom.detect_layout(conf['layout'], flashrom_size)
            if not layout:
                raise error.TestError('Cannot detect flash rom layout.')

            # enable write protection
            if self.verbose:
                print ' - Enable Write Protection for %s' % conf['name']
            if layout.keys().count('ro') != 1:
                raise error.TestError("INTERNAL ERROR: Must be 1 RO section")
            if not self.flashrom.enable_write_protect(layout, 'ro'):
                raise error.TestError('ERROR: cannot enable write protection.')

        # restore default selection.
        if not self.flashrom.select_target(system_default_selection):
            raise error.TestError('ERROR: cannot restore target.')
        print " - Complete."


if __name__ == "__main__":
    print "please run this program with autotest."
