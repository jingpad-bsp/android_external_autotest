# Copyright 2014 The Chromium OS Authors. All rights reserved.
# Use of this source code is governed by a BSD-style license that can be
# found in the LICENSE file.

import time

from autotest_lib.client.common_lib import error
from autotest_lib.client.common_lib.cros.network import interface
from autotest_lib.client.common_lib.cros.network import iw_runner
from autotest_lib.client.common_lib.cros.network import netblock
from autotest_lib.client.common_lib.cros.network import ping_runner
from autotest_lib.client.common_lib.cros.network import xmlrpc_security_types
from autotest_lib.client.common_lib.cros.tendo import privetd_helper
from autotest_lib.server import site_linux_router
from autotest_lib.server import test
from autotest_lib.server.cros.network import hostap_config

PASSPHRASE = 'chromeos'
PRIVET_AP_STARTUP_TIMEOUT_SECONDS = 30


class privetd_PrivetSetupFlow(test.test):
    """This test validates the privet pairing/authentication/setup flow."""
    version = 1

    def warmup(self, host, router_hostname=None):
        self._router = None
        self._privet_config = privetd_helper.PrivetdConfig(
                log_verbosity=3,
                enable_ping=True,
                wifi_bootstrap_mode=privetd_helper.BOOTSTRAP_CONFIG_AUTOMATIC,
                disable_pairing_security=True)
        self._privet_config.restart_with_config(host=host)
        self._router = site_linux_router.build_router_proxy(
                test_name=self.__class__.__name__,
                client_hostname=host.hostname,
                router_addr=router_hostname)


    def cleanup(self, host):
        privetd_helper.PrivetdConfig.naive_restart(host=host)
        if self._router is not None:
            self._router.close()


    def run_once(self, host):
        helper = privetd_helper.PrivetdHelper(host=host)
        helper.ping_server()  # Make sure the server is up and running.

        # We should see a bootstrapping network broadcasting from the device.
        scan_interface = self._router.get_wlanif(2437, 'managed')
        self._router.host.run('%s link set %s up' %
                              (self._router.cmd_ip, scan_interface))
        start_time = time.time()
        privet_bss = None
        while time.time() - start_time < PRIVET_AP_STARTUP_TIMEOUT_SECONDS:
            bss_list = self._router.iw_runner.scan(scan_interface)
            for bss in bss_list or []:
                if self._privet_config.is_softap_ssid(bss.ssid):
                    privet_bss = bss
        if privet_bss is None:
            raise error.TestFail('Device did not start soft AP in time.')
        self._router.release_interface(scan_interface)

        # Get the netblock of the interface running the AP.
        dut_iw_runner = iw_runner.IwRunner(remote_host=host)
        devs = dut_iw_runner.list_interfaces(desired_if_type='AP')
        if not devs:
            raise error.TestFail('No AP devices on DUT?')
        ap_interface = interface.Interface(devs[0].if_name, host=host)
        ap_netblock = netblock.from_addr(ap_interface.ipv4_address_and_prefix)

        # Set up an AP on the router in the 5Ghz range with WPA2 security.
        wpa_config = xmlrpc_security_types.WPAConfig(
                psk=PASSPHRASE,
                wpa_mode=xmlrpc_security_types.WPAConfig.MODE_PURE_WPA2,
                wpa2_ciphers=[xmlrpc_security_types.WPAConfig.CIPHER_CCMP])
        router_conf = hostap_config.HostapConfig(
                frequency=5240, security_config=wpa_config,
                mode=hostap_config.HostapConfig.MODE_11N_PURE)
        self._router.hostap_configure(router_conf)

        # Connect the other interface on the router to the AP on the client
        # at a hardcoded IP address.
        self._router.configure_managed_station(
                privet_bss.ssid, privet_bss.frequency,
                ap_netblock.get_addr_in_block(200))
        self._router.ping(ping_runner.PingConfig(ap_netblock.addr, count=3))


        raise error.TestNAError('Finished implemented part of test.')
        # TODO(wiley): The following:
        #   Use avahi-browse to look around from the router and find privet
        #       mDNS records.
        #   Use ip/port information in those records to call the /info API.
        #   Then call /pairing/start
        #   Then call /pairing/finish
        #   Then call /setup/start
        #   Confirm that the AP on the client goes down
        #   Confirm that the client connects to the AP in the 5Ghz range.
