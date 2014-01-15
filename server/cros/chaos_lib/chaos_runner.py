# Copyright (c) 2013 The Chromium OS Authors. All rights reserved.
# Use of this source code is governed by a BSD-style license that can be
# found in the LICENSE file.

import contextlib
import datetime
import logging
import random

from autotest_lib.client.common_lib import error
from autotest_lib.client.common_lib.cros.network import chaos_constants
from autotest_lib.client.common_lib.cros.network import iw_runner
from autotest_lib.server import hosts
from autotest_lib.server import frontend
from autotest_lib.server import site_linux_system
from autotest_lib.server.cros import host_lock_manager
from autotest_lib.server.cros.chaos_ap_configurators import ap_batch_locker
from autotest_lib.server.cros.chaos_ap_configurators import ap_cartridge
from autotest_lib.server.cros.chaos_ap_configurators import ap_spec
from autotest_lib.server.cros.network import wifi_client


class ChaosRunner(object):
    """Object to run a network_WiFi_ChaosXXX test."""


    def __init__(self, test, host, spec):
        """Initializes and runs test.

        @param test: a string, test name.
        @param host: an Autotest host object, device under test.
        @param spec: an APSpec object

        """
        self._test = test
        self._host = host
        self._ap_spec = spec
        # Log server and DUT times
        dt = datetime.datetime.now()
        logging.info('Server time: %s', dt.strftime('%a %b %d %H:%M:%S %Y'))
        logging.info('DUT time: %s', self._host.run('date').stdout.strip())


    @staticmethod
    def _allocate_packet_capturer(lock_manager, hostname):
        """Allocates a machine to capture packets.

        Locks the allocated machine if the machine was discovered via AFE
        to prevent tests stomping on each other.

        @param lock_manager HostLockManager object.
        @param hostname string optional hostname of a packet capture machine.

        """
        if hostname is not None:
            return hosts.SSHHost(hostname)

        afe = frontend.AFE(debug=True)
        potential_hosts = afe.get_hosts(multiple_labels=['packet_capture'])
        if not potential_hosts:
            raise error.TestError('No packet capture machines available.')

        # Shuffle hosts so that we don't lock the same packet capture host
        # every time.  This prevents errors where a fault might seem repeatable
        # because we lock the same packet capturer for each test run.
        random.shuffle(potential_hosts)
        for host in potential_hosts:
            if lock_manager.lock([host.hostname]):
                logging.info('Locked packet capture host %s.', host.hostname)
                return hosts.SSHHost(host.hostname + '.cros')
            else:
                logging.info('Unable to lock packet capture host %s.',
                             host.hostname)

        raise error.TestError('Could not allocate a packet tracer.')


    def _power_down_aps(self, aps):
         """Powers down a list of aps.

         @param aps: a list of APConfigurator objects.

         """
         cartridge = ap_cartridge.APCartridge()
         for ap in aps:
             ap.power_down_router()
             cartridge.push_configurator(ap)
         cartridge.run_configurators()


    def _configure_aps(self, aps):
        """Configures a given list of APs.

        @param aps: a list of APConfigurator objects.

        """
        cartridge = ap_cartridge.APCartridge()
        for ap in aps:
            ap.set_using_ap_spec(self._ap_spec)
            cartridge.push_configurator(ap)
        cartridge.run_configurators()


    def _return_available_networks(self, ap, capturer, wifi_if, job):
        """Returns a list of networks configured as described by an APSpec.

        @param ap: the APConfigurator being testing against.
        @param capturer: a packet capture device
        @param wifi_if: string of the wifi interface to use
        @param job: an Autotest job object.

        @returns a list of the network available; otherwise None

        """
        logging.info('Searching for SSID %s in scan...', ap.ssid)
        # We have some APs that need a while to come on-line
        networks = capturer.iw_runner.wait_for_scan_result(wifi_if,
                                                           ssid=ap.ssid,
                                                           timeout_seconds=300)
        if networks == None:
            # For crbug.com/331915, the next step will be to reboot the DUT
            logging.error('Scan failed to run, see crbug.com/309148.')
            return None

        if len(networks) == 0:
            # The SSID of the AP was not found
            logging.error('The ssid %s was not found in the scan', ap.ssid)
            job.run_test('network_WiFi_ChaosConfigFailure', ap=ap,
                         error_string=chaos_constants.AP_SSID_NOTFOUND,
                         tag=ap.ssid)
            return None

        # Sanitize the only security setting that doesn't match
        # before doing the comparison
        security = networks[0].security
        if security == iw_runner.SECURITY_MIXED:
            security = iw_runner.SECURITY_WPA2

        if security != self._ap_spec.security:
            # Check if AP is configured with the expected security.
            logging.error('%s was the expected security but got %s',
                          self._ap_spec.security, security)
            job.run_test('network_WiFi_ChaosConfigFailure', ap=ap,
                         error_string=chaos_constants.AP_SECURITY_MISMATCH,
                         tag=ap.ssid)
            return None
        return networks


    def _release_ap(self, ap, batch_locker):
        """Powers down and unlocks the given AP.

        @param ap: the APConfigurator under test
        @param batch_locker: the batch locker object

        """
        ap.power_down_router()
        ap.apply_settings()
        batch_locker.unlock_one_ap(ap.host_name)


    def _sanitize_client(self):
        """Clean up logs and reboot the DUT."""
        self._host.run('rm -rf /var/log')
        self._host.reboot()


    def run(self, job, batch_size=15, tries=10, capturer_hostname=None):
        """Executes Chaos test.

        @param job: an Autotest job object.
        @param batch_size: an integer, max number of APs to lock in one batch.
        @param tries: an integer, number of iterations to run per AP.
        @param capturer_hostname: a string or None, hostname or IP of capturer.

        """

        logging.debug('Going to cleanup logs and reboot host!!!')
        self._sanitize_client()

        lock_manager = host_lock_manager.HostLockManager()
        with host_lock_manager.HostsLockedBy(lock_manager):
            capture_host = self._allocate_packet_capturer(
                    lock_manager, hostname=capturer_hostname)
            capturer = site_linux_system.LinuxSystem(capture_host, {},
                                                     'packet_capturer')
            batch_locker = ap_batch_locker.ApBatchLocker(lock_manager,
                                                         self._ap_spec)
            while batch_locker.has_more_aps():
                with contextlib.closing(wifi_client.WiFiClient(
                    hosts.create_host(self._host.hostname),
                    './debug')) as client:

                    aps = batch_locker.get_ap_batch(batch_size=batch_size)
                    if not aps:
                        logging.info('No more APs to test.')
                        break

                    # Power down all of the APs because some can get grumpy
                    # if they are configured several times and remain on.
                    # User the cartridge to down group power downs and
                    # configurations.
                    self._power_down_aps(aps)
                    self._configure_aps(aps)

                    for ap in aps:
                        # http://crbug.com/306687
                        if ap.ssid == None:
                            logging.error('The SSID was not set for the AP:%s',
                                          ap)

                        if not ap.get_configuration_success():
                            logging.error('The AP %s was not configured '
                                          'correctly', ap.ssid)
                            job.run_test('network_WiFi_ChaosConfigFailure',
                                         ap=ap,
                                         error_string=
                                             chaos_constants.AP_CONFIG_FAIL,
                                         tag=ap.ssid)
                            continue

                        # Setup a managed interface to perform scanning on the
                        # packet capture device.
                        wifi_if = capturer.get_wlanif(
                            ap_spec.FREQUENCY_TABLE[self._ap_spec.channel],
                            'managed')
                        capturer.host.run('%s link set %s up' %
                                          (capturer.cmd_ip, wifi_if))
                        networks = self._return_available_networks(ap,
                                                                   capturer,
                                                                   wifi_if,
                                                                   job)
                        capturer.remove_interface(wifi_if)

                        if not networks:
                            self._release_ap(ap, batch_locker)
                            continue

                        assoc_params = ap.get_association_parameters()
                        result = job.run_test(self._test,
                                     capturer=capturer,
                                     capturer_frequency=networks[0].frequency,
                                     capturer_ht_type=networks[0].ht,
                                     host=self._host,
                                     assoc_params=assoc_params,
                                     client=client,
                                     tries=tries,
                                     debug_info=ap.name,
                                     # Copy all logs from the system
                                     disabled_sysinfo=False,
                                     tag=ap.ssid)

                        self._release_ap(ap, batch_locker)

                batch_locker.unlock_aps()
