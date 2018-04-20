# Copyright 2018 The Chromium OS Authors. All rights reserved.
# Use of this source code is governed by a BSD-style license that can be
# found in the LICENSE file.

import logging
import shutil
import time

from autotest_lib.client.bin import test, utils
from autotest_lib.client.common_lib import error

class UpdateEngineTest(test.test):
    """Base class for update engine client tests."""

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

    # Files used by the tests.
    _UPDATE_ENGINE_LOG = '/var/log/update_engine.log'
    _UPDATE_ENGINE_LOG_DIR = '/var/log/update_engine/'
    _CUSTOM_LSB_RELEASE = '/mnt/stateful_partition/etc/lsb-release'

    _UPDATE_ENGINE_PREFS_FOLDER = '/var/lib/update_engine/prefs/'

    # Public key used to force update_engine to verify omaha response data on
    # test images.
    _IMAGE_PUBLIC_KEY = 'LS0tLS1CRUdJTiBQVUJMSUMgS0VZLS0tLS0KTUlJQklqQU5CZ2txaGtpRzl3MEJBUUVGQUFPQ0FROEFNSUlCQ2dLQ0FRRUFxZE03Z25kNDNjV2ZRenlydDE2UQpESEUrVDB5eGcxOE9aTys5c2M4aldwakMxekZ0b01Gb2tFU2l1OVRMVXArS1VDMjc0ZitEeElnQWZTQ082VTVECkpGUlBYVXp2ZTF2YVhZZnFsalVCeGMrSlljR2RkNlBDVWw0QXA5ZjAyRGhrckduZi9ya0hPQ0VoRk5wbTUzZG8Kdlo5QTZRNUtCZmNnMUhlUTA4OG9wVmNlUUd0VW1MK2JPTnE1dEx2TkZMVVUwUnUwQW00QURKOFhtdzRycHZxdgptWEphRm1WdWYvR3g3K1RPbmFKdlpUZU9POUFKSzZxNlY4RTcrWlppTUljNUY0RU9zNUFYL2xaZk5PM1JWZ0cyCk83RGh6emErbk96SjNaSkdLNVI0V3daZHVobjlRUllvZ1lQQjBjNjI4NzhxWHBmMkJuM05wVVBpOENmL1JMTU0KbVFJREFRQUIKLS0tLS1FTkQgUFVCTElDIEtFWS0tLS0tCg=='


    def cleanup(self):
        # Make sure to grab the update engine log for every test run.
        shutil.copy(self._UPDATE_ENGINE_LOG, self.resultsdir)

        # Ensure ethernet adapters are back on
        self._enable_internet()


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
            if self._UPDATE_STATUS_UPDATED_NEED_REBOOT == status[
                self._CURRENT_OP]:
                raise error.TestFail('Update status was NEED_REBOOT while '
                                     'trying to get download status.')
            # If we call this right after reboot it may not be downloading yet.
            if self._UPDATE_ENGINE_DOWNLOADING != status[self._CURRENT_OP]:
                time.sleep(1)
                continue
            return float(status[self._PROGRESS])


    def _wait_for_update_to_complete(self):
        """Checks if the update has got to FINALIZING status."""
        while True:
            status = self._get_update_engine_status()

            # During reboot, status will be None
            if status is not None:
                if status[self._CURRENT_OP] == self._UPDATE_STATUS_IDLE:
                    raise error.TestFail('Update status was unexpectedly '
                                         'IDLE when we were waiting for the '
                                         'update to complete. Please check '
                                         'the update engine logs.')
                statuses = [self._UPDATE_ENGINE_FINALIZING,
                            self._UPDATE_STATUS_UPDATED_NEED_REBOOT]
                if any(arg in status[self._CURRENT_OP] for arg in statuses):
                    break
            time.sleep(1)


    def _get_update_engine_status(self):
        """Returns a dictionary version of update_engine_client --status"""
        status = utils.run('update_engine_client --status', ignore_timeout=True)
        if status is None:
            return None
        logging.debug(status)
        status_dict = {}
        for line in status.stdout.splitlines():
            entry = line.partition('=')
            status_dict[entry[0]] = entry[2]
        return status_dict


    def _check_update_engine_log_for_entry(self, entry, raise_error=False):
        """
        Checks for entries in the update_engine log.

        @param entry: The line to search for.
        @param raise_error: Fails tests if log doesn't contain entry.

        @return Boolean if the update engine log contains the entry.

        """
        result = utils.run('cat %s | grep "%s"' % (self._UPDATE_ENGINE_LOG,
                                                   entry), ignore_status=True)

        if result.exit_status != 0:
            if raise_error:
                raise error.TestFail('Did not find expected string in %s: %s' %
                    (self._UPDATE_ENGINE_LOG, entry))
            else:
                return False
        return True


    def _enable_internet(self, ping_server='google.com'):
        """
        Re-enables the internet connection.

        @param ping_server: The server to ping to check we are online.

        """
        utils.run('ifconfig eth0 up', ignore_status=True)
        utils.run('ifconfig eth1 up', ignore_status=True)
        utils.start_service('recover_duts', ignore_status=True)

        # We can't return right after reconnecting the network or the server
        # test may not receive the message. So we wait a bit longer for the
        # DUT to be reconnected.
        utils.poll_for_condition(lambda: utils.ping(ping_server,
                                                    deadline=5, timeout=5) == 0,
                                 timeout=60,
                                 sleep_interval=1)


    def _disable_internet(self):
        """Disable the internet connection"""
        try:
            # DUTs in the lab have a service called recover_duts that is used to
            # check that the DUT is online and if it is not it will bring it
            # back online. We will need to stop this service for the length
            # of this test.
            utils.stop_service('recover_duts', ignore_status=True)
            utils.run('ifconfig eth0 down')
            utils.run('ifconfig eth1 down', ignore_status=True)
        except error.CmdError:
            logging.exception('Failed to disconnect one or more interfaces.')


    def _check_for_update(self, port, server='http://127.0.0.1',
                          interactive=True):
        """
        Starts a background update check.

        @param port: The omaha port to call in the update url.
        @param interactive: Whether we are doing an interactive update.

        """
        cmd = 'update_engine_client --check_for_update --omaha_url=' + \
              '%s:%d/update ' % (server, port)
        if not interactive:
            cmd += ' --interactive=false'

        utils.run(cmd, ignore_status=True)


    def _wait_for_update_to_fail(self):
        """Waits for the update to retry until failure."""
        while True:
            if self._check_update_engine_log_for_entry('Reached max attempts ',
                                                       raise_error=False):
                break
            time.sleep(1)
