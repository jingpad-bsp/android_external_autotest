# Copyright (c) 2010 The Chromium OS Authors. All rights reserved.
# Use of this source code is governed by a BSD-style license that can be
# found in the LICENSE file.

import logging, os, socket, time, zipfile

from autotest_lib.client.common_lib import error, chromiumos_updater
from autotest_lib.server import autotest, test, autoupdate_utils

IGNORE_PATTERNS = ('*.pyc', '^.git', '^.gitignore')
POLL_INTERVAL = 5

class autoupdate_Host(test.test):
    version = 1

    def run_once(self, host=None, image_path=None):
        localhost = socket.gethostname()
        base_update_url='http://%s:%s' % (localhost,
                                          autoupdate_utils.DEVSERVER_PORT)
        logging.info('Using image at: %s' % image_path)
        logging.info('Base update url: %s' % base_update_url)

        # Initiate chromiumos_updater and retrieve old release version.
        updater = chromiumos_updater.ChromiumOSUpdater(host, base_update_url)
        old_release = updater.get_build_id()

        # Setup client machine by overriding lsb-release.
        client_host = autotest.Autotest(host)
        client_host.run_test('autoupdate_SetUp', devserver=base_update_url)

        image_name = 'chromiumos_test_image.bin'

        tester = autoupdate_utils.AutoUpdateTester(image_path)

        # Generate update payload and write to devserver static directory.
        tester.generate_update_payload()

        # Starts devserver.
        devserver = tester.start_devserver()

        # Initiate update process on client.
        update_engine_client_cmd = ('update_engine_client '
                                    '--app_version ForcedUpdate')
        logging.info('Start update process on %s' % host.hostname)
        logging.info('Issuing command: %s' % update_engine_client_cmd)
        host.run(update_engine_client_cmd)

        boot_id = host.get_boot_id()
        logging.info('Client boot_id: %s' % boot_id)

        # Poll update process until it completes.
        status = chromiumos_updater.UPDATER_IDLE
        while status != chromiumos_updater.UPDATER_NEED_REBOOT:
            status = updater.check_update_status()
            if status == chromiumos_updater.UPDATER_IDLE:
                raise error.TestFail('Could not initiate update process on client.')
            logging.info('Update status: %s' % status)
            time.sleep(POLL_INTERVAL)

        # Remove override lsb-release and reboot.
        logging.info('Update completed, remove lsb-release and reboot machine')
        host.run('rm /mnt/stateful_partition/etc/lsb-release')
        host.reboot()

        host.wait_for_restart(old_boot_id=boot_id)

        new_release = updater.get_build_id()
        logging.info('old release: %s' % old_release)
        logging.info('new release: %s' % new_release)

        if new_release == old_release:
            raise error.TestFail('Failed to update')

        # Terminate devserver.
        tester.kill_devserver(devserver)
