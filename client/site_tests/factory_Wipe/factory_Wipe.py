# Copyright (c) 2010 The Chromium OS Authors. All rights reserved.
# Use of this source code is governed by a BSD-style license that can be
# found in the LICENSE file.

import os

from autotest_lib.client.bin import factory
from autotest_lib.client.bin import test, utils
from autotest_lib.client.common_lib import error


class factory_Wipe(test.test):
    version = 3

    def wipe_stateful_partition(self, secure_wipe):
        # Stub test to switch to boot from the release image,
        # and tag stateful partition to indicate wipe on reboot.
        os.chdir(self.srcdir)

        factory.log('switch to boot from release image and prepare wipe')

        # Switch to the release image.
        utils.run('./switch_partitions.sh')

        # Tag the current image to be wiped according to preference
        # (secure or fast). Don't tag until partition switch passes.
        tag_filename = '/mnt/stateful_partition/factory_install_reset'
        if secure_wipe:
            utils.run('touch %s' % tag_filename)
        else:
            utils.run('echo "fast" > %s' % tag_filename)

        # Copy the wipe splash image to state partition.
        utils.run('cp -f wipe_splash.png /mnt/stateful_partition/')
        # Time for reboot.
        utils.run('shutdown -r now')

    def run_once(self,
                 secure_wipe,
                 status_file_path=None,
                 test_list=None,
                 only_run_from_factory_finalize_unless_testing=True):

        test_name = factory.FINAL_VERIFICATION_TEST_UNIQUE_NAME
        if only_run_from_factory_finalize_unless_testing:
            if factory.lookup_status_by_unique_name(
                    test_name, test_list, status_file_path) != factory.PASSED:
                raise error.TestFail('You need to pass %s first.' % test_name)
        else:
            factory.log('WARNING: Final Verification is bypassed.\n' +
                        'THIS DEVICE CANNOT BE QUALIFIED.')

        self.wipe_stateful_partition(secure_wipe)
