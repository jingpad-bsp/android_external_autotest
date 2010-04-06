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
            'atom-proto': {'gpio_read': self.pinetrail_gpio_read,
                           'recovery': 6, 'developer': 7, 'fwwp': 10},
        }


    def setup(self):
        self.job.setup_dep(['iotools'])
        # create a empty srcdir to prevent the error that checks .version file
        if not os.path.exists(self.srcdir):
          os.mkdir(self.srcdir)


    def run_once(self):
        self.init_sku_table()
        dep = 'iotools'
        dep_dir = os.path.join(self.autodir, 'deps', dep)
        self.job.install_pkg(dep, 'dep', dep_dir)

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
          self.recovery_gpio = table['recovery']
          self.developer_gpio = table['developer']
          self.fwwp_gpio = table['fwwp']
        else:
          raise error.TestError('System settings not defined for board %s' %
                                systemsku)

        recovery, developer, fwwp = self.gpio_read()

        keyvals = {}
        keyvals['level_recovery'] = recovery
        keyvals['level_developer'] = developer
        keyvals['level_firmware_writeprotect'] = fwwp

        self.write_perf_keyval(keyvals)


    # Returns (recovery, developer, fwwp).
    # Throws exception on error.
    def pinetrail_gpio_read(self):
        path = self.autodir + '/deps/iotools/'
        # Generate symlinks for iotools.
        utils.system(path + 'iotools --make-links')

        # Tigerpoint LPC Interface.
        tp_device = (0, 31, 0)
        # TP io port location of GPIO registers.
        tp_GPIOBASE = 0x48
        # IO offset to check GPIO levels.
        tp_GP_LVL_off = 0xc

        tp_gpio_iobase_str = utils.system_output(path +
            'pci_read32 %s %s %s %s' % (
            tp_device[0], tp_device[1], tp_device[2], tp_GPIOBASE))
        # Bottom bit of GPIOBASE is a flag indicating io space.
        tp_gpio_iobase = long(tp_gpio_iobase_str, 16) & ~1

        tp_gpio_mask_str = utils.system_output(path +
            'io_read32 %s' % (
            tp_gpio_iobase + tp_GP_LVL_off))

        tp_gpio_mask = long(tp_gpio_mask_str, 16)
        recovery = (tp_gpio_mask >> self.recovery_gpio) & 1
        developer = (tp_gpio_mask >> self.developer_gpio) & 1
        fwwp = (tp_gpio_mask >> self.fwwp_gpio) & 1

        return recovery, developer, fwwp
