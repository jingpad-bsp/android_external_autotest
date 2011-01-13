# Copyright (c) 2010 The Chromium OS Authors. All rights reserved.
# Use of this source code is governed by a BSD-style license that can be
# found in the LICENSE file.

import logging, time

from autotest_lib.client.common_lib import error
from autotest_lib.client.common_lib.cros import autoupdater
from autotest_lib.server import autotest, test, autoupdate_utils

POLL_INTERVAL = 5

class autoupdate_Host(test.test):
    version = 1

    def run_once(self, host=None, image_path=None):
        tester = autoupdate_utils.AutoUpdateTester()
        logging.info('Using image at: %s' % image_path)
        logging.info('Base update url: %s' % tester.get_devserver_url())

        # Initiate autoupdater and retrieve old release version.
        updater = autoupdater.ChromiumOSUpdater(host,
                                                tester.get_devserver_url())
        old_release = updater.get_build_id()

        image_name = 'chromiumos_test_image.bin'

        # Setup client machine by overriding lsb-release.
        client_host = autotest.Autotest(host)
        client_host.run_test('autoupdate_SetUp',
                             devserver=tester.get_devserver_url())

        # Starts devserver.
        tester.start_devserver(image_path)

        # Initiate update process on client.
        update_engine_client_cmd = ('update_engine_client '
                                    '--app_version ForcedUpdate')
        logging.info('Start update process on %s' % host.hostname)
        logging.info('Issuing command: %s' % update_engine_client_cmd)
        host.run(update_engine_client_cmd)

        boot_id = host.get_boot_id()
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
        host.run('rm /mnt/stateful_partition/etc/lsb-release')
        host.reboot()

        host.wait_for_restart(old_boot_id=boot_id)

        # Terminate devserver.
        tester.kill_devserver()

        new_release = updater.get_build_id()
        logging.info('old release: %s' % old_release)
        logging.info('new release: %s' % new_release)

        if new_release == old_release:
            raise error.TestFail('Failed to update')

