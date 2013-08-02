# Copyright (c) 2013 The Chromium OS Authors. All rights reserved.
# Use of this source code is governed by a BSD-style license that can be
# found in the LICENSE file.

import logging, time
from autotest_lib.client.bin import test, utils
from autotest_lib.client.common_lib import error
from autotest_lib.client.cros import constants, cros_ui

class desktopui_Respawn(test.test):
    """Validate that the UI will cease respawning after a certain number of
       attempts in a time window. By design, this test does _not_ attempt to
       ensure that these values remain the same over time. The values are
       somewhat arbitrary anyhow, so enforcing them is simply an over-constraint.
    """
    version = 1

    UNREASONABLY_HIGH_RESPAWN_COUNT = 90

    def _nuke_ui_with_prejudice_and_wait(self, timeout):
        """Nuke the UI with prejudice, then wait for it to come up.

        @param timeout: time in seconds to wait for browser to come back."""
        utils.nuke_process_by_name(constants.SESSION_MANAGER,
                                   with_prejudice=True)
        utils.poll_for_condition(cros_ui.is_up,
                                 desc='ui to come up',
                                 timeout=timeout)


    def run_once(self):
        # Ensure the UI is running.
        logging.debug('Restarting UI to ensure that it\'s running.')
        cros_ui.stop(allow_fail=True)
        cros_ui.start(wait_for_login_prompt=False)

        # Nuke the UI continuously until it stops respawning.
        respawned_at_least_once = False
        attempt = 0
        timeout_seconds = 10
        start_time = time.time()
        try:
            for attempt in range(self.UNREASONABLY_HIGH_RESPAWN_COUNT):
                self._nuke_ui_with_prejudice_and_wait(timeout_seconds)
                respawned_at_least_once = True
        except utils.TimeoutError as te:
            start_time += timeout_seconds
            pass
        logging.info("Respawned UI %d times in %d seconds",
                     attempt, time.time() - start_time)

        if cros_ui.is_up():
            raise error.TestFail(
                'Respawning should have stopped before %d attempts' %
                self.UNREASONABLY_HIGH_RESPAWN_COUNT)
        if not respawned_at_least_once:
            raise error.TestFail('Should have respawned at least once')


    def cleanup(self):
        # If the UI is already up, we want to tolerate that.
        cros_ui.start(allow_fail=True)
