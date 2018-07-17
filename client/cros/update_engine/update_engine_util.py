# Copyright 2018 The Chromium OS Authors. All rights reserved.
# Use of this source code is governed by a BSD-style license that can be
# found in the LICENSE file.

import logging
import os
import time

from autotest_lib.client.common_lib import error

class UpdateEngineUtil(object):
    """Utility code shared between client and server update_engine autotests"""

    # Update engine status lines.
    _LAST_CHECKED_TIME = 'LAST_CHECKED_TIME'
    _PROGRESS = 'PROGRESS'
    _CURRENT_OP = 'CURRENT_OP'
    _NEW_VERSION = 'NEW VERSION'
    _NEW_SIZE = 'NEW_SIZE'

    # Update engine statuses.
    _UPDATE_STATUS_IDLE = 'UPDATE_STATUS_IDLE'
    _UPDATE_ENGINE_DOWNLOADING = 'UPDATE_STATUS_DOWNLOADING'
    _UPDATE_ENGINE_FINALIZING = 'UPDATE_STATUS_FINALIZING'
    _UPDATE_STATUS_UPDATED_NEED_REBOOT = 'UPDATE_STATUS_UPDATED_NEED_REBOOT'
    _UPDATE_STATUS_REPORTING_ERROR_EVENT = 'UPDATE_STATUS_REPORTING_ERROR_EVENT'

    # Files used by the tests.
    _UPDATE_ENGINE_LOG = '/var/log/update_engine.log'
    _UPDATE_ENGINE_LOG_DIR = '/var/log/update_engine/'
    _CUSTOM_LSB_RELEASE = '/mnt/stateful_partition/etc/lsb-release'
    _UPDATE_ENGINE_PREFS_DIR = '/var/lib/update_engine/prefs/'

    # Public key used to force update_engine to verify omaha response data on
    # test images.
    _IMAGE_PUBLIC_KEY = 'LS0tLS1CRUdJTiBQVUJMSUMgS0VZLS0tLS0KTUlJQklqQU5CZ2txaGtpRzl3MEJBUUVGQUFPQ0FROEFNSUlCQ2dLQ0FRRUFxZE03Z25kNDNjV2ZRenlydDE2UQpESEUrVDB5eGcxOE9aTys5c2M4aldwakMxekZ0b01Gb2tFU2l1OVRMVXArS1VDMjc0ZitEeElnQWZTQ082VTVECkpGUlBYVXp2ZTF2YVhZZnFsalVCeGMrSlljR2RkNlBDVWw0QXA5ZjAyRGhrckduZi9ya0hPQ0VoRk5wbTUzZG8Kdlo5QTZRNUtCZmNnMUhlUTA4OG9wVmNlUUd0VW1MK2JPTnE1dEx2TkZMVVUwUnUwQW00QURKOFhtdzRycHZxdgptWEphRm1WdWYvR3g3K1RPbmFKdlpUZU9POUFKSzZxNlY4RTcrWlppTUljNUY0RU9zNUFYL2xaZk5PM1JWZ0cyCk83RGh6emErbk96SjNaSkdLNVI0V3daZHVobjlRUllvZ1lQQjBjNjI4NzhxWHBmMkJuM05wVVBpOENmL1JMTU0KbVFJREFRQUIKLS0tLS1FTkQgUFVCTElDIEtFWS0tLS0tCg=='


    def _wait_for_progress(self, progress):
        """
        Waits until we reach the percentage passed as the input.

        @param progress: The progress [0.0 .. 1.0] we want to wait for.
        """
        while True:
            completed = self._get_update_progress()
            logging.debug('Checking if %s is greater than %s', completed,
                          progress)
            if completed >= progress:
                break
            time.sleep(1)


    def _is_update_started(self):
        """Checks if the update has started."""
        status = self._get_update_engine_status()
        if status is None:
            return False
        return any(arg == status[self._CURRENT_OP] for arg in
            [self._UPDATE_ENGINE_DOWNLOADING, self._UPDATE_ENGINE_FINALIZING])


    def _get_update_progress(self):
        """Returns the current payload downloaded progress."""
        while True:
            status = self._get_update_engine_status()
            if not status:
                continue
            if self._UPDATE_STATUS_IDLE == status[self._CURRENT_OP]:
                raise error.TestFail('Update status was idle while trying to '
                                     'get download status.')
            if self._UPDATE_STATUS_REPORTING_ERROR_EVENT == status[
                self._CURRENT_OP]:
                raise error.TestFail('Update status reported error.')
            if self._UPDATE_STATUS_UPDATED_NEED_REBOOT == status[
                self._CURRENT_OP]:
                raise error.TestFail('Update status was NEEDS_REBOOT while '
                                     'trying to get download status.')
            # If we call this right after reboot it may not be downloading yet.
            if self._UPDATE_ENGINE_DOWNLOADING != status[self._CURRENT_OP]:
                time.sleep(1)
                continue
            return float(status[self._PROGRESS])


    def _wait_for_update_to_fail(self):
        """Waits for the update to retry until failure."""
        timeout_minutes = 20
        timeout = time.time() + 60 * timeout_minutes
        while True:
            if self._check_update_engine_log_for_entry('Reached max attempts ',
                                                       raise_error=False):
                break
            time.sleep(1)
            if time.time() > timeout:
                raise error.TestFail('Update did not fail as expected. Timeout'
                                     ': %d minutes.' % timeout_minutes)



    def _wait_for_update_to_complete(self, finalizing_ok=False):
        """
        Checks if the update has completed.

        @param finalizing_ok: FINALIZING status counts as complete.

        """
        statuses = [self._UPDATE_STATUS_UPDATED_NEED_REBOOT]
        if finalizing_ok:
            statuses.append(self._UPDATE_ENGINE_FINALIZING)
        while True:
            status = self._get_update_engine_status()

            # During reboot, status will be None
            if status is not None:
                if self._UPDATE_STATUS_REPORTING_ERROR_EVENT == status[
                    self._CURRENT_OP]:
                    raise error.TestFail('Update status reported error.')
                if status[self._CURRENT_OP] == self._UPDATE_STATUS_IDLE:
                    raise error.TestFail('Update status was unexpectedly '
                                         'IDLE when we were waiting for the '
                                         'update to complete. Please check '
                                         'the update engine logs.')
                if any(arg in status[self._CURRENT_OP] for arg in statuses):
                    break
            time.sleep(1)


    def _get_update_engine_status(self, timeout=3600, ignore_status=True):
        """Returns a dictionary version of update_engine_client --status"""
        status = self._run('update_engine_client --status', timeout=timeout,
                           ignore_timeout=True, ignore_status=ignore_status)
        if status is None:
            return None
        logging.debug(status)
        status_dict = {}
        for line in status.stdout.splitlines():
            entry = line.partition('=')
            status_dict[entry[0]] = entry[2]
        return status_dict


    def _check_update_engine_log_for_entry(self, entry, raise_error=False,
                                           err_str=None,
                                           update_engine_log=None):
        """
        Checks for entries in the update_engine log.

        @param entry: The line to search for.
        @param raise_error: Fails tests if log doesn't contain entry.
        @param err_str: The error string to raise if we cannot find entry.
        @param update_engine_log: Update engine log string you want to
                                  search. If None, we will read from the
                                  current update engine log.

        @return Boolean if the update engine log contains the entry.

        """
        if update_engine_log:
            result = self._run('echo "%s" | grep "%s"' % (update_engine_log,
                                                          entry),
                               ignore_status=True)
        else:
            result = self._run('cat %s | grep "%s"' % (
                self._UPDATE_ENGINE_LOG, entry), ignore_status=True)

        if result.exit_status != 0:
            if raise_error:
                error_str = 'Did not find expected string in update_engine ' \
                            'log: %s' % entry
                logging.debug(error_str)
                raise error.TestFail(err_str if err_str else error_str)
            else:
                return False
        return True


    def _update_continued_where_it_left_off(self, progress):
        """
        Checks that the update did not restart after an interruption.

        @param progress: The progress the last time we checked.

        @returns True if update continued. False if update restarted.

        """
        completed = self._get_update_progress()
        logging.info('New value: %f, old value: %f', completed, progress)
        return completed >= progress


    def _check_for_update(self, server='http://127.0.0.1', port=8082,
                          interactive=True, ignore_status=False,
                          wait_for_completion=False):
        """
        Starts a background update check.

        @param server: The omaha server to call in the update url.
        @param port: The omaha port to call in the update url.
        @param interactive: True if we are doing an interactive update.
        @param ignore_status: True if we should ignore exceptions thrown.
        @param wait_for_completion: True for --update, False for
                                    --check_for_update.
        """
        update = 'update' if wait_for_completion else 'check_for_update'
        cmd = 'update_engine_client --%s --omaha_url=%s:%d/update ' % (update,
                                                                       server,
                                                                       port)

        if not interactive:
          cmd += ' --interactive=false'
        self._run(cmd, ignore_status=ignore_status)


    def _save_extra_update_engine_logs(self, number_of_logs=2):
        """
        Get the last X number of update_engine logs on the DUT.

        @param number_of_logs: The number of logs to save.

        """
        files = self._run('ls -t -1 %s' %
                          self._UPDATE_ENGINE_LOG_DIR).stdout.splitlines()

        for i in range(number_of_logs if number_of_logs <= len(files) else
                       len(files)):
            file = os.path.join(self._UPDATE_ENGINE_LOG_DIR, files[i])
            self._get_file(file, self.resultsdir)


    def _get_second_last_update_engine_log(self):
        """
        Gets second last update engine log text.

        This is useful for getting the last update engine log before a reboot.

        """
        files = self._run('ls -t -1 %s' %
                          self._UPDATE_ENGINE_LOG_DIR).stdout.splitlines()
        return self._run('cat %s%s' % (self._UPDATE_ENGINE_LOG_DIR,
                                       files[1])).stdout
