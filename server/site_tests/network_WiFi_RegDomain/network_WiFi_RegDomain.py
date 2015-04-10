# Copyright (c) 2015 The Chromium OS Authors. All rights reserved.
# Use of this source code is governed by a BSD-style license that can be
# found in the LICENSE file.

import logging
import tempfile

from autotest_lib.client.bin import utils
from autotest_lib.client.common_lib import error
from autotest_lib.client.common_lib.cros.network import xmlrpc_datatypes
from autotest_lib.server import test
from autotest_lib.server.cros.network import hostap_config
from autotest_lib.server.cros.network import wifi_test_context_manager


class network_WiFi_RegDomain(test.test):
    """Verifies that a DUT connects, or fails to connect, on particular
    channels, in particular regions, per expectations."""
    version = 1


    REBOOT_TIMEOUT = 60
    VPD_CACHE_FILE = \
        '/mnt/stateful_partition/unencrypted/cache/vpd/full-v2.txt'
    VPD_CLEAN_COMMAND ='dump_vpd_log --clean'


    def fake_up_region(self, region):
        """Modifies VPD cache to force a particular region, and reboots system
        into to faked state.

        @param region: The region we want to force the host into.

        """
        self.host.run(self.VPD_CLEAN_COMMAND)
        temp_vpd = tempfile.NamedTemporaryFile()
        temp_vpd.write('"region"="%s"' % region)
        temp_vpd.flush()
        self.host.send_file(temp_vpd.name, self.VPD_CACHE_FILE)
        self.host.reboot(timeout=self.REBOOT_TIMEOUT, wait=True)


    def warmup(self, host, raw_cmdline_args, additional_params):
        """Stash away parameters for use by run_once().

        @param host Host object representing the client DUT.
        @param raw_cmdline_args Raw input from autotest.
        @param additional_params One item from CONFIGS in control file.

        """
        self.host = host
        self.cmdline_args = utils.args_to_dict(raw_cmdline_args)
        self.configuration = additional_params


    def test_channel(self, wifi_context, channel_config):
        """Verifies that a DUT does/does not connect on a particular channel,
        per expectation.

        @param wifi_context: A WiFiTestContextManager.
        @param channel_config: A dict with 'number' and 'expect_connect' keys.
        """

        try:
            router_conf = hostap_config.HostapConfig(
                channel=channel_config['number'],
                mode=hostap_config.HostapConfig.MODE_11N_MIXED)
            client_conf = xmlrpc_datatypes.AssociationParameters(
                expect_failure=not channel_config['expect_connect'])
            wifi_context.configure(router_conf)
            wifi_context.router.start_capture(router_conf.frequency)
            client_conf.ssid = wifi_context.router.get_ssid()
            # TODO(quiche): Maybe use a shorter timeout for
            # failure cases.
            wifi_context.assert_connect_wifi(client_conf)
            wifi_context.client.shill.delete_entries_for_ssid(
                client_conf.ssid)
            return True
        except error.TestFail:
            logging.error('Verification failed for %s', channel_config)
            return False
        finally:
            wifi_context.router.stop_capture()


    def run_once(self):
        """Configures a DUT to behave as if it was manufactured for a
        particular region, and verifies that it connects, or fails to
        connect, per expectations.

        """

        region = self.configuration['region']
        success = True
        try:
            self.fake_up_region(self.configuration['region'])
            wifi_context = wifi_test_context_manager.WiFiTestContextManager(
                self.__class__.__name__,
                self.host,
                self.cmdline_args,
                self.debugdir)
            with wifi_context:
                for channel_config in self.configuration['channels']:
                    if not self.test_channel(wifi_context, channel_config):
                        success = False
            if not success:
                raise error.TestFail(
                    'Verification failed for some channel configs (see below)')
        finally:
            self.host.run(self.VPD_CLEAN_COMMAND)
            self.host.reboot(timeout=self.REBOOT_TIMEOUT, wait=True)
