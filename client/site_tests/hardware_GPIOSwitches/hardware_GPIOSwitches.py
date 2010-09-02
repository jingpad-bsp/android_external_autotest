# -*- coding: utf-8 -*-
#
# Copyright (c) 2010 The Chromium OS Authors. All rights reserved.
# Use of this source code is governed by a BSD-style license that can be
# found in the LICENSE file.

__author__ = 'nsanders@chromium.org (Nick Sanders)'

import logging, os

from autotest_lib.client.bin import test, utils
from autotest_lib.client.common_lib import error

class hardware_GPIOSwitches(test.test):
    version = 1


    def init_sku_table(self):
        self.sku_table = {
            # SKU: gpio_read, recovery GPIO, developer mode,
            # firmware writeprotect
            'atom-proto': {'gpio_read': self.acpi_gpio_read}
            }

    def initialize(self, gpio_root='/home/gpio'):
        # setup gpio's for reading.  Must re-create after each POR
        if os.path.exists(gpio_root):
            utils.system("rm -rf %s" % gpio_root)
        utils.system("mkdir %s" % (gpio_root))
        try:
            utils.system("/usr/sbin/gpio_setup")
        except error.CmdError:
            raise error.TestNAError('GPIO setup failed\nGPIO 設定失敗')
        self._gpio_root=gpio_root

    def run_once(self):
        self.init_sku_table()

        # TODO(nsanders): Detect actual system type here by HWQual ID (?)
        # and redirect to the correct check.
        # We're just checking for any Atom here, and hoping for the best.
        try:
          utils.system('cat /proc/cpuinfo | grep "model name" | '
                       'grep -qe "N4[0-9][0-9]"')
          systemsku = 'atom-proto'
        except:
          systemsku = 'unknown'

        # Look up hardware configuration.
        if systemsku in self.sku_table:
          table = self.sku_table[systemsku]
          self.gpio_read = table['gpio_read']
        else:
          raise error.TestError('System settings not defined for board %s' %
                                systemsku)


        keyvals = {}
        keyvals['level_recovery'] = self.gpio_read('recovery_button')
        keyvals['level_developer'] = self.gpio_read('developer_switch')
        keyvals['level_firmware_writeprotect'] = self.gpio_read('write_protect')

        self.write_perf_keyval(keyvals)

    def acpi_gpio_read(self, name):
        return int(utils.system_output("cat %s/%s" % (self._gpio_root, name)))
