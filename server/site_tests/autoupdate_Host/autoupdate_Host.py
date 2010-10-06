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

    def assert_is_file(self, path):
        if not os.path.isfile(path):
            raise error.TestError('%s is not a file' % path)

    def assert_is_zip(self, path):
        """Raise exception if path is not a zip file.
        """
        self.assert_is_file(path)
        if not zipfile.is_zipfile(path):
            raise error.TestError('%s is not a zip file' % path)

    def run_once(self, host=None, image_path=None):
        localhost = socket.gethostname()
        base_update_url='http://%s:%s' % (localhost,
                                          autoupdate_utils.DEVSERVER_PORT)
        logging.info('Using image at: %s' % image_path)
        logging.info('Base update url: %s' % base_update_url)
        self.assert_is_zip(image_path)

        # Setup client machine by overriding lsb-release.
        client_host = autotest.Autotest(host)
        client_host.run_test('autoupdate_SetUp', devserver=base_update_url)

        cwd = os.getcwd()
        devserver_bin = os.path.join(cwd, 'dev')
        devserver_src = os.path.join('/home', os.environ['USER'], 'trunk',
                                     'src', 'platform', 'dev')
        devserver_static = os.path.join(devserver_bin, 'static')
        image_name = 'chromiumos_test_image.bin'

        # Copy devserver source into current working directory.
        os.system('cp -r %s %s' % (devserver_src, cwd))

        # Extract test image.
        autoupdate_utils.extract_image(image_path, image_name, cwd)
        test_image = os.path.join(cwd, image_name)

        # Generate update payload and write to devserver static directory.
        self.assert_is_file(test_image)
        payload_path = os.path.join(devserver_static, 'update.gz')
        autoupdate_utils.generate_update_payload(test_image, payload_path)

        omaha_config = os.path.join(devserver_bin, 'autest.conf')
        autoupdate_utils.make_omaha_config(omaha_config, 'autest', payload_path)

        # Starts devserver.
        devserver = autoupdate_utils.start_devserver(devserver_bin,
                                                     omaha_config)
        if devserver is None:
            error.TestFail('Please kill devserver before running test.')

        # Initiate update process on client.
        update_engine_client_cmd = ('update_engine_client '
                                    '--app_version ForcedUpdate')
        logging.info('Start update process on %s' % host.hostname)
        logging.info('Issuing command: %s' % update_engine_client_cmd)
        host.run(update_engine_client_cmd)

        boot_id = host.get_boot_id()
        logging.info('Client boot_id: %s' % boot_id)

        # Poll update process until it completes.
        updater = chromiumos_updater.ChromiumOSUpdater(host, base_update_url)
        status = chromiumos_updater.UPDATER_IDLE
        while status != chromiumos_updater.UPDATER_NEED_REBOOT:
            status = updater.check_update_status()
            if status == chromiumos_updater.UPDATER_IDLE:
                error.TestFail('Could not initiate update process on client.')
            logging.info('Update status: %s' % status)
            time.sleep(POLL_INTERVAL)

        # Remove override lsb-release and reboot.
        logging.info('Update completed, remove lsb-release and reboot machine')
        host.run('rm /mnt/stateful_partition/etc/lsb-release')
        host.reboot()

        host.wait_for_restart(old_boot_id=boot_id)

        image_release = image_path.split('-')[1]
        new_release = updater.get_build_id().split('=')[0]
        logging.info('image release: %s' % image_release)
        logging.info('new release: %s' % new_release)

        if not new_release.startswith(image_release):
            error.TestFail('New release %s is not %s.'
                           % (new_release, image_release))

        # Terminate devserver.
        autoupdate_utils.kill_devserver(devserver)
