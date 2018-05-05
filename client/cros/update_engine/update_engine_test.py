# Copyright 2018 The Chromium OS Authors. All rights reserved.
# Use of this source code is governed by a BSD-style license that can be
# found in the LICENSE file.

import logging
import shutil

from autotest_lib.client.bin import test, utils
from autotest_lib.client.common_lib import error
from autotest_lib.client.cros.update_engine import update_engine_util

class UpdateEngineTest(test.test, update_engine_util.UpdateEngineUtil):
    """Base class for update engine client tests."""

    def initialize(self):
        self._internet_was_disabled = False

        # Define functions to be used in update_engine_util.
        self._run = utils.run
        self._get_file = shutil.copy


    def cleanup(self):
        # Make sure to grab the update engine log for every test run.
        shutil.copy(self._UPDATE_ENGINE_LOG, self.resultsdir)

        # Ensure ethernet adapters are back on
        self._enable_internet()


    def _enable_internet(self, ping_server='google.com'):
        """
        Re-enables the internet connection.

        @param ping_server: The server to ping to check we are online.

        """
        if not self._internet_was_disabled:
            return

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


    def _disable_internet(self, ping_server='google.com'):
        """Disable the internet connection"""
        self._internet_was_disabled = True
        try:
            # DUTs in the lab have a service called recover_duts that is used to
            # check that the DUT is online and if it is not it will bring it
            # back online. We will need to stop this service for the length
            # of this test.
            utils.stop_service('recover_duts', ignore_status=True)
            utils.run('ifconfig eth0 down')
            utils.run('ifconfig eth1 down', ignore_status=True)

            # Make sure we are offline
            utils.poll_for_condition(lambda: utils.ping(ping_server,
                                                        deadline=5,
                                                        timeout=5) != 0,
                                     timeout=60,
                                     sleep_interval=1,
                                     desc='Ping failure while offline.')
        except (error.CmdError, utils.TimeoutError):
            logging.exception('Failed to disconnect one or more interfaces.')
            logging.debug(utils.run('ifconfig', ignore_status=True))
            raise error.TestFail('Disabling the internet connection failed.')

