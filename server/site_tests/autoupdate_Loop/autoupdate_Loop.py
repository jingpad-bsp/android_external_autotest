# Copyright (c) 2010 The Chromium OS Authors. All rights reserved.
# Use of this source code is governed by a BSD-style license that can be
# found in the LICENSE file.

import logging, time

from autotest_lib.client.common_lib import error
from autotest_lib.client.common_lib.cros import autoupdater
from autotest_lib.server import autotest, test, autoupdate_utils

POLL_INTERVAL = 5

class autoupdate_Loop(test.test):
    version = 1

    def update(self, image_path):
        # Initiate autoupdater and retrieve old release version.
        updater = autoupdater.ChromiumOSUpdater(self.host,
                                                self.tester.get_devserver_url())
        old_release = updater.get_build_id()

        image_name = 'chromiumos_test_image.bin'

        # Setup client machine by overriding lsb-release.
        client_host = autotest.Autotest(self.host)
        client_host.run_test('autoupdate_SetUp',
                             devserver=self.tester.get_devserver_url())

        # Starts devserver.
        self.tester.start_devserver(image_path)

        # Initiate update process on client.
        update_engine_client_cmd = ('update_engine_client '
                                    '--app_version ForcedUpdate')
        logging.info('Start update process on %s' % self.host.hostname)
        logging.info('Issuing command: %s' % update_engine_client_cmd)
        self.host.run(update_engine_client_cmd)

        boot_id = self.host.get_boot_id()
        logging.info('Client boot_id: %s' % boot_id)

        # Poll update process until it completes.
        status = autoupdater.UPDATER_IDLE
        while status != autoupdater.UPDATER_NEED_REBOOT:
            status = updater.check_update_status()
            if status == autoupdater.UPDATER_IDLE:
                raise error.TestFail('Failed to start update process.')
            logging.info('Update status: %s' % status)
            time.sleep(POLL_INTERVAL)

        # Remove override lsb-release and reboot.
        logging.info('Update completed, remove lsb-release and reboot machine')
        self.host.run('rm /mnt/stateful_partition/etc/lsb-release')
        self.host.reboot()

        self.host.wait_for_restart(old_boot_id=boot_id)

        # Terminate devserver.
        self.tester.kill_devserver()

        new_release = updater.get_build_id()
        logging.info('old release: %s' % old_release)
        logging.info('new release: %s' % new_release)


    def run_once(self, host=None, start=None, target=None, iteration=5):
        if not start:
            error.TestFail('No --start_image specified.')

        if not target:
            error.TestFail('No --target_image specified.')

        self.host = host
        self.tester = autoupdate_utils.AutoUpdateTester()

        logging.info('Using start image: %s' % start)
        logging.info('Using target image: %s' % target)
        logging.info('Base update url: %s' % self.tester.get_devserver_url())
        logging.info('Iterating %s times' % iteration)

        # Update machine to start image
        logging.info('Updating machine to start image: %s' % start)
        self.update(start)

        # Loop upgrade/revert between start and target images
        i = 1
        while i <= int(iteration):
            logging.info('Iteration %s/%s: updating machine  to %s' %
                         (i, iteration, target))
            self.update(target)
            logging.info('Iteration %s/%s: reverting machine to %s' %
                         (i, iteration, start))
            self.update(start)
            i = i + 1
