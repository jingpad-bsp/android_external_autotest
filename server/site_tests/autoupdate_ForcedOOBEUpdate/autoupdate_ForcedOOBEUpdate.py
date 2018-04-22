# Copyright 2017 The Chromium OS Authors. All rights reserved.
# Use of this source code is governed by a BSD-style license that can be
# found in the LICENSE file.

import logging
import random
import time

from autotest_lib.client.common_lib import error
from autotest_lib.client.common_lib.cros import tpm_utils
from autotest_lib.server.cros.update_engine import update_engine_test
from chromite.lib import retry_util

class autoupdate_ForcedOOBEUpdate(update_engine_test.UpdateEngineTest):
    """Runs a forced autoupdate during OOBE."""
    version = 1


    def cleanup(self):
        self._host.run('rm %s' % self._CUSTOM_LSB_RELEASE, ignore_status=True)

        # Get the last two update_engine logs: before and after reboot.
        files = self._host.run('ls -t -1 %s' %
                               self._UPDATE_ENGINE_LOG_DIR).stdout.splitlines()
        for i in range(2):
            self._host.get_file('%s%s' % (self._UPDATE_ENGINE_LOG_DIR,
                                          files[i]), self.resultsdir)
        cmd = 'update_engine_client --update_over_cellular=no'
        retry_util.RetryException(error.AutoservRunError, 2, self._host.run,
                                  cmd)
        super(autoupdate_ForcedOOBEUpdate, self).cleanup()


    def _wait_for_oobe_update_to_complete(self):
        """Wait for the update that started to complete.

        Repeated check status of update. It should move from DOWNLOADING to
        FINALIZING to COMPLETE (then reboot) to IDLE.
        """
        while True:
            status = self._get_update_engine_status()

            # During reboot, status will be None
            if status is not None:
                if self._UPDATE_STATUS_IDLE == status[self._CURRENT_OP]:
                    break
            time.sleep(1)


    def run_once(self, host, full_payload=True, cellular=False,
                 interrupt=False, max_updates=1, job_repo_url=None):
        """
        Runs a forced autoupdate during ChromeOS OOBE.

        @param host: The DUT that we are running on.
        @param full_payload: True for a full payload. False for delta.
        @param cellular: True to do the update over a cellualar connection.
                         Requires that the DUT have a sim card slot.
        @param interrupt: True to interrupt the update in the middle.
        @param max_updates: Used to tell the test how many times it is
                            expected to ping its omaha server.
        @param job_repo_url: Used for debugging locally. This is used to figure
                             out the current build and the devserver to use.
                             The test will read this from a host argument
                             when run in the lab.

        """
        self._host = host
        tpm_utils.ClearTPMOwnerRequest(self._host)

        # veyron_rialto is a medical device with a different OOBE that auto
        # completes so this test is not valid on that device.
        if 'veyron_rialto' in self._host.get_board():
            raise error.TestNAError('Rialto has a custom OOBE. Skipping test.')

        update_url = self.get_update_url_for_test(job_repo_url,
                                                  full_payload=full_payload,
                                                  critical_update=True,
                                                  public=cellular,
                                                  max_updates=max_updates)
        logging.info('Update url: %s', update_url)
        before = self._get_chromeos_version()
        payload_info = None
        if cellular:
            cmd = 'update_engine_client --update_over_cellular=yes'
            retry_util.RetryException(error.AutoservRunError, 2, self._host.run,
                                      cmd)
            # Get the payload's information (size, SHA256 etc) since we will be
            # setting up our own omaha instance on the DUT. We pass this to
            # the client test.
            payload = self._get_payload_url(full_payload=full_payload)
            staged_url = self._stage_payload_by_uri(payload)
            payload_info = self._get_staged_file_info(staged_url)

        # Call client test to start the forced OOBE update.
        self._run_client_test_and_check_result('autoupdate_StartOOBEUpdate',
                                               image_url=update_url,
                                               public=cellular,
                                               payload_info=payload_info,
                                               full_payload=full_payload)


        if interrupt:
            # Choose a random downloaded progress to interrupt the update.
            progress = random.uniform(0.1, 0.8)
            logging.debug('Progress when we will interrupt: %f', progress)
            self._wait_for_progress(progress)
            logging.info('We will start interrupting the update.')
            completed = self._get_update_progress()

            # Reboot the DUT during the update.
            self._host.reboot()
            if not self._update_continued_where_it_left_off(completed):
                raise error.TestFail('The update did not continue where it '
                                     'left off before rebooting.')
            completed = self._get_update_progress()

            self._disconnect_then_reconnect_network(update_url)
            if not self._update_continued_where_it_left_off(completed):
                raise error.TestFail('The update did not continue where it '
                                     'left off before disconnecting network.')
            completed = self._get_update_progress()

            # Suspend / Resume
            self._suspend_then_resume()
            if not self._update_continued_where_it_left_off(completed):
                raise error.TestFail('The update did not continue where it '
                                     'left off after suspend/resume.')

        self._wait_for_oobe_update_to_complete()

        if cellular:
            # We didn't have a devserver so we cannot check the hostlog to
            # ensure the update completed successfully. Instead we can check
            # that the second-to-last update engine log has the successful
            # update message. Second to last because its the one before OOBE
            # rebooted.
            update_engine_files_cmd = 'ls -t -1 %s' % \
                                      self._UPDATE_ENGINE_LOG_DIR
            files = self._host.run(update_engine_files_cmd).stdout.splitlines()
            before_reboot_file = self._host.run('cat %s%s' % (
                self._UPDATE_ENGINE_LOG_DIR, files[1])).stdout
            self._check_for_cellular_entries_in_update_log(before_reboot_file)

            success = 'Update successfully applied, waiting to reboot.'
            update_ec = self._host.run('cat %s%s | grep '
                                       '"%s"' % (self._UPDATE_ENGINE_LOG_DIR,
                                                 files[1], success)).exit_status
            if update_ec != 0:
                raise error.TestFail('We could not verify that the update '
                                     'completed successfully. Check the logs.')
            return

        # Verify that the update completed successfully by checking hostlog.
        rootfs_hostlog, reboot_hostlog = self._create_hostlog_files()
        self.verify_update_events(self._CUSTOM_LSB_VERSION, rootfs_hostlog)
        self.verify_update_events(self._CUSTOM_LSB_VERSION, reboot_hostlog,
                                  self._CUSTOM_LSB_VERSION)

        after = self._get_chromeos_version()
        logging.info('Successfully force updated from %s to %s.', before, after)
