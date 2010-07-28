# Copyright (c) 2010 The Chromium OS Authors. All rights reserved.
# Use of this source code is governed by a BSD-style license that can be
# found in the LICENSE file.

import os

from autotest_lib.client.bin import factory
from autotest_lib.client.bin import factory_ui_lib as ful
from autotest_lib.client.bin import test, utils
from autotest_lib.client.common_lib import error


GPIO_ROOT = '/home/gpio'


def init_gpio(gpio_root=GPIO_ROOT):
    """ initializes GPIO in GPIO_ROOT """
    if os.path.exists(gpio_root):
        utils.system("rm -rf '%s'" % gpio_root)
    utils.system("mkdir '%s'" % (gpio_root))
    utils.system("/usr/sbin/gpio_setup")


class factory_Wipe(test.test):
    version = 2

    def wipe_stateful_partition(self, secure_wipe):
        # Stub test to switch to boot from the release image,
        # and tag stateful partition to indicate wipe on reboot.
        os.chdir(self.srcdir)

        factory.log('switch to boot from release image and prepare wipe')

        # Tag the current image to be wiped according to preference
        # (secure or fast).
        tag_filename = '/mnt/stateful_partition/factory_install_reset'
        if secure_wipe:
            utils.run('touch %s' % tag_filename)
        else:
            utils.run('echo "fast" > %s' % tag_filename)

        # Copy the wipe splash image to state partition.
        utils.run('cp -f wipe_splash.png /mnt/stateful_partition/')
        # Switch to the release image.
        utils.run('./switch_partitions.sh')
        # Time for reboot.
        utils.run('shutdown -r now')

    def check_developer_switch(self, do_check):
        if not do_check:
            factory.log('WARNING: DEVELOPER SWITCH BUTTON ' +
                        'IS NOT TESTED/ENABLED!');
            return True

        init_gpio()
        status = open(os.path.join(GPIO_ROOT, "developer_switch")).read()
        status_val = int(status)
        if status_val != 0:
            raise error.TestFail('Developer Switch Button is enabled')

    def flashrom_write_protect(self, do_check):
        # enable write protection (and test it) for flashrom

        if not do_check:
            factory.log('WARNING: FLASHROM WRITE PROTECTION ' +
                        'IS NOT TESTED/ENABLED!');
            return True

        factory.log('enable write protect (factory_EnableWriteProtect)')
        self.job.run_test('factory_EnableWriteProtect')

        # verify if write protection range is properly fixed,
        # and all bits in RW is writable.
        factory.log('verify write protect (hardware_EepromWriteProtect)')
        if not self.job.run_test('hardware_EepromWriteProtect'):
            raise error.TestFail('Flashrom write protection test failed.')

    def run_once(self,
                 check_developer_switch,
                 secure_wipe,
                 write_protect,
                 status_file_path=None,
                 test_list=None):
        # first, check if all previous tests are passed.
        status_map = ful.StatusMap(status_file_path, test_list)
        failed = status_map.filter(ful.FAILED)
        if failed:
            raise error.TestFail('Some tests were failed. Cannot start wipe.')

        # apply each final tests
        self.check_developer_switch(check_developer_switch)
        self.flashrom_write_protect(write_protect)
        self.wipe_stateful_partition(secure_wipe)
