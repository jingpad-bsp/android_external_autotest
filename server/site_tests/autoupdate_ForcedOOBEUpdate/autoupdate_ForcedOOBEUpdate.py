# Copyright 2017 The Chromium OS Authors. All rights reserved.
# Use of this source code is governed by a BSD-style license that can be
# found in the LICENSE file.
import json
import logging
import os
import time

from autotest_lib.client.common_lib import error
from autotest_lib.client.common_lib import lsbrelease_utils
from autotest_lib.client.common_lib.cros import dev_server
from autotest_lib.server import autotest
from autotest_lib.server.cros.dynamic_suite import tools
from autotest_lib.server.cros.update_engine import omaha_devserver
from autotest_lib.server.cros.update_engine import update_engine_test


class autoupdate_ForcedOOBEUpdate(update_engine_test.UpdateEngineTest):
    """Runs a forced autoupdate during OOBE."""
    version = 1

    # We override the default lsb-release file.
    _CUSTOM_LSB_RELEASE = '/mnt/stateful_partition/etc/lsb-release'

    # Version we tell the DUT it is on before update.
    _CUSTOM_LSB_VERSION = '0.0.0.0'

    # Expected hostlog events during update: 4 during rootfs
    _ROOTFS_HOSTLOG_EVENTS = 4


    def setup(self):
        self._omaha_devserver = None


    def cleanup(self):
        if self._omaha_devserver is not None:
            self._omaha_devserver.stop_devserver()
        self._host.run('rm %s' % self._CUSTOM_LSB_RELEASE, ignore_status=True)

        # Get the last two update_engine logs: before and after reboot.
        files = self._host.run('ls -t -1 '
                               '/var/log/update_engine/').stdout.splitlines()
        for i in range(2):
            self._host.get_file('/var/log/update_engine/%s' % files[i],
                                self.resultsdir)


    def _get_chromeos_version(self):
        """Read the ChromeOS version from /etc/lsb-release."""
        lsb = self._host.run('cat /etc/lsb-release').stdout
        return lsbrelease_utils.get_chromeos_release_version(lsb)


    def _get_payload_url_from_job_repo_url(self, job_repo_url):
        """Get the payload to update to.

        We will use the job_repo_url to get a payload that matches the build
        number that the DUT is currently running. That way we will update
        from N->N at OOBE.

        @param job_repo_url: a url you can pass to the test for local debugging.
        """
        if job_repo_url is None:
            info = self._host.host_info_store.get()
            job_repo_url = info.attributes.get(
                self._host.job_repo_url_attribute, '')
        if not job_repo_url:
            raise error.TestFail('There was no job_repo_url so we cannot get '
                                 'a payload to use.')
        ds_url, build = tools.get_devserver_build_from_package_url(job_repo_url)
        self._autotest_devserver = dev_server.ImageServer(ds_url)
        self._autotest_devserver.stage_artifacts(build, ['full_payload'])
        payload_url = self._autotest_devserver.get_full_payload_url(build)

        # The devserver adds on the update.gz filename again during
        # HandleUpdatePing() so we take it off here.
        return payload_url.rpartition('/')[0]


    def _create_hostlog_files(self):
        """Create the two hostlog files for the update.

        To ensure the update was succesful we need to compare the update
        events against expected update events. There is a hostlog for the
        rootfs update and for the post reboot update check.
        """
        hostlog = self._omaha_devserver.get_hostlog(self._host.ip,
                                                    wait_for_reboot_events=True)
        logging.info('Hostlog: %s', hostlog)

        # File names to save the hostlog events to.
        rootfs_hostlog = os.path.join(self.resultsdir, 'hostlog_rootfs')
        reboot_hostlog = os.path.join(self.resultsdir, 'hostlog_reboot')

        with open(rootfs_hostlog, 'w') as outfile:
            json.dump(hostlog[:self._ROOTFS_HOSTLOG_EVENTS], outfile)
        with open(reboot_hostlog, 'w') as outfile:
            json.dump(hostlog[self._ROOTFS_HOSTLOG_EVENTS:], outfile)
        return rootfs_hostlog, reboot_hostlog


    def _wait_for_update_to_complete(self):
        """Wait for the update that started to complete.

        Repeated check status of update. It should move from DOWNLOADING to
        FINALIZING to COMPLETE to IDLE.
        """
        while True:
            status = self._host.run('update_engine_client --status',
                                    ignore_timeout=True,
                                    timeout=10)

            # During reboot, status will be None
            if status is not None:
                status = status.stdout.splitlines()
                logging.debug(status)
                if "UPDATE_STATUS_IDLE" in status[2]:
                    break
            time.sleep(1)


    def run_once(self, host, job_repo_url=None):
        self._host = host

        # Get a payload that matches the current build on the DUT.
        update_url = self._get_payload_url_from_job_repo_url(job_repo_url)
        logging.info('Payload url to use: %s', update_url)

        # Start a devserver in the lab that will serve a critical update.
        self._omaha_devserver = omaha_devserver.OmahaDevserver(
            self._autotest_devserver.hostname, update_url)
        self._omaha_devserver.start_devserver()

        before = self._get_chromeos_version()

        # Call client test to start the forced OOBE update.
        client_at = autotest.Autotest(self._host)
        client_at.run_test('autoupdate_StartOOBEUpdate',
                           image_url=self._omaha_devserver.get_update_url())

        # Don't continue the test if the client failed for any reason.
        client_at._check_client_test_result(self._host,
                                            'autoupdate_StartOOBEUpdate')

        self._wait_for_update_to_complete()

        # Verify that the update completed successfully by checking hostlog.
        rootfs_hostlog, reboot_hostlog = self._create_hostlog_files()
        self.verify_update_events(self._CUSTOM_LSB_VERSION, rootfs_hostlog)
        self.verify_update_events(self._CUSTOM_LSB_VERSION, reboot_hostlog,
                                  self._CUSTOM_LSB_VERSION)

        after = self._get_chromeos_version()
        logging.info('Successfully force updated from %s to %s.', before, after)
