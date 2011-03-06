# -*- coding: utf-8 -*-
#
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
    version = 2
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
                'trust_fmap': False,
            }, { # Embedded Controller
                'name': 'EC',
                'layout': 'ro|rw',
                'target': 'ec',
                'trust_fmap': True,
                'fmap_conversion': {
                        'EC_RO': 'ro',
                        'EC_RW': 'rw',
                },
            }, )

        # always restore system flashrom selection to this one
        system_default_selection = 'bios'

        for conf in eeprom_sets:
            # select target
            if not self.flashrom.select_target(conf['target']):
                raise error.TestError(
                        'ERROR: cannot select target %s\n'
                        '錯誤: 無法選取快閃記憶體目標 %s' %
                        (conf['name'], conf['name']))

            # build layout
            flashrom_size = self.flashrom.get_size()
            if not flashrom_size:
                raise error.TestError(
                        'Cannot get flash rom size.\n'
                        '無法取得快閃記憶體大小')
            layout = None
            if conf['trust_fmap']:
                if self.verbose:
                    print ' - Trying to use FMAP layout for %s' % conf['name']
                image = self.flashrom.read_whole()
                assert flashrom_size == len(image)
                layout = flashrom_util.decode_fmap_layout(
                        conf['fmap_conversion'], image)
                if 'ro' not in layout:
                    layout = None
                else:
                    if self.verbose:
                        print ' - Using layout by FMAP in %s' % conf['name']

            if not layout:
                # do not trust current image when detecting layout.
                layout = self.flashrom.detect_layout(conf['layout'],
                                                     flashrom_size, None)
                if self.verbose:
                    print ' - Using hard-coded layout for %s' % conf['name']
            if not layout:
                raise error.TestError(
                        'Cannot detect flash rom layout.\n'
                        '無法偵測快閃記憶體配置結構')

            # verify if the layout is half of firmware.
            if (layout['ro'][1] - layout['ro'][0] + 1) != (flashrom_size / 2):
                raise error.TestError(
                        'Invalid RO section in flash rom layout.\n'
                        '快閃記憶體唯讀區段配置錯誤。')

            # enable write protection
            if self.verbose:
                print ' - Enable Write Protection for %s' % conf['name']
            if layout.keys().count('ro') != 1:
                raise error.TestError(
                        "INTERNAL ERROR: Must be 1 RO section\n"
                        "內部錯誤: 須要單一個唯讀區段")
            # only configure (enable) write protection if current status is not
            # correct, because sometimes the factory test is executed several
            # times without resetting WP status.
            if not self.flashrom.verify_write_protect(layout, 'ro'):
                if not (self.flashrom.enable_write_protect(layout, 'ro') and
                        self.flashrom.verify_write_protect(layout, 'ro')):
                    raise error.TestError(
                            'ERROR: cannot enable write protection.\n'
                            '錯誤: 無法啟用寫入保護')

            # check write protection
            if self.verbose:
                print ' - Check Write Protection for %s' % conf['name']
            self.flashrom.disable_write_protect()
            if not self.flashrom.verify_write_protect(layout, 'ro'):
                raise error.TestError(
                        'ERROR: not write-protected (modifiable status).\n'
                        '錯誤: 寫入保護不正常 (狀況可被改變)')

        # restore default selection.
        if not self.flashrom.select_target(system_default_selection):
            raise error.TestError(
                    'ERROR: cannot restore target.\n'
                    '錯誤: 無法還原快閃記憶體目標')
        print " - Complete."


if __name__ == "__main__":
    print "please run this program with autotest."
