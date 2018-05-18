# Copyright 2017 The Chromium OS Authors. All rights reserved.
# Use of this source code is governed by a BSD-style license that can be
# found in the LICENSE file.

import logging

from autotest_lib.client.common_lib import error
from autotest_lib.client.common_lib import utils
from autotest_lib.server.cros.network import hostap_config
from autotest_lib.server.cros.network import wifi_cell_test_base

class network_WiFi_Reset(wifi_cell_test_base.WiFiCellTestBase):
    """Test that the WiFi interface can be reset successfully, and that WiFi
    comes back up properly. Also run a few suspend/resume cycles along the way.
    Supports only Marvell (mwifiex) Wifi drivers.
    """

    version = 1

    _MWIFIEX_RESET_PATH = "/sys/kernel/debug/mwifiex/%s/reset"
    _MWIFIEX_RESET_TIMEOUT = 20
    _MWIFIEX_RESET_INTERVAL = 0.5
    _NUM_RESETS = 15
    _NUM_SUSPENDS = 5
    _SUSPEND_DELAY = 10


    @property
    def mwifiex_reset_path(self):
        """Get path to the Wifi interface's reset file."""
        return self._MWIFIEX_RESET_PATH % self.context.client.wifi_if


    def mwifiex_reset_exists(self):
        """Check if the mwifiex reset file is present (i.e., a mwifiex
        interface is present).
        """
        return self.context.client.host.run('test -e "%s"' %
                self.mwifiex_reset_path, ignore_status=True).exit_status == 0


    def mwifiex_reset(self):
        """Perform mwifiex reset and wait for the interface to come back up."""

        ssid = self.context.router.get_ssid()

        # Adapter will asynchronously reset.
        self.context.client.host.run('echo 1 > ' + self.mwifiex_reset_path)

        # Wait for disconnect. We aren't guaranteed to receive a disconnect
        # event, but shill will at least notice the adapter went away.
        self.context.client.wait_for_service_states(ssid, ['idle'],
                timeout_seconds=20)

        # Now wait for the reset interface file to come back.
        utils.poll_for_condition(
                condition=self.mwifiex_reset_exists,
                exception=error.TestFail(
                        'Failed to reset device %s' %
                        self.context.client.wifi_if),
                timeout=self._MWIFIEX_RESET_TIMEOUT,
                sleep_interval=self._MWIFIEX_RESET_INTERVAL)


    def run_once(self):
        """Body of the test."""

        if not self.mwifiex_reset_exists():
            self._supports_reset = False
            raise error.TestNAError('DUT does not support device reset')
        else:
            self._supports_reset = True

        client = self.context.client
        ap_config = hostap_config.HostapConfig(channel=1)
        ssid = self.configure_and_connect_to_ap(ap_config)

        self.context.assert_ping_from_dut()

        router = self.context.router
        ssid = router.get_ssid()

        boot_id = client.host.get_boot_id()

        logging.info("Running %d suspends", self._NUM_SUSPENDS)
        for _ in range(self._NUM_SUSPENDS):
            logging.info("Running %d resets", self._NUM_RESETS)
            for __ in range(self._NUM_RESETS):
                self.mwifiex_reset()
                client.wait_for_connection(ssid)
                self.context.assert_ping_from_dut()

            client.do_suspend(self._SUSPEND_DELAY)
            client.host.test_wait_for_resume(boot_id)
            client.wait_for_connection(ssid)


    def cleanup(self):
        """Performs cleanup at exit. May reboot the DUT, to keep the system
        functioning for the next test.
        """

        if self._supports_reset and not self.mwifiex_reset_exists():
            logging.info("Test exited, but interface is missing; rebooting")
            self.context.client.reboot(timeout=60)
