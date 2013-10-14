# Copyright (c) 2013 The Chromium OS Authors. All rights reserved.
# Use of this source code is governed by a BSD-style license that can be
# found in the LICENSE file.

import logging
import datetime
import random
import time

from autotest_lib.server import hosts
from autotest_lib.server import frontend
from autotest_lib.server import site_linux_system
from autotest_lib.server.cros import host_lock_manager
from autotest_lib.server.cros.chaos_ap_configurators import ap_batch_locker
from autotest_lib.server.cros.chaos_ap_configurators import ap_cartridge


class ChaosRunner(object):
    """Object to run a network_WiFi_ChaosXXX test."""


    def __init__(self, test, host, wifi_client, ap_spec):
        """Initializes and runs test.

        @param test: a string, test name.
        @param host: an Autotest host object, device under test.
        @param wifi_client: a WiFiClient object
        @param ap_spec: an APSpec object

        """
        self._test = test
        self._host = host
        self._wifi_client = wifi_client
        self._ap_spec = ap_spec
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


    def verify_bss_in_scan(self, bss):
        """Runs a scan on the DUT and verifies the SSID is being broadcasted.

        @param bss: the BSS to scan for

        @returns True is the SSID is found; false otherwise

        """
        scan_bss = '%s %s scan' % (self._wifi_client.command_iw,
                                   self._wifi_client.wifi_if)
        start_time = int(time.time())
        # Setting 300s as timeout
        logging.info('Waiting for the DUT to find BSS %s... ', bss)
        while (int(time.time()) - start_time) < 300:
           # If command failed: Device or resource busy (-16), run again.
           scan_result = self._wifi_client.host.run(scan_bss,
                                                    ignore_status=True)
           if 'busy' in str(scan_result):
               continue
           if bss in str(scan_result):
               logging.debug('Found bss %s in scan', bss)
               return True
           else:
               continue
        return False


    def run(self, job, batch_size=15, tries=10, capturer_hostname=None):
        """Executes Chaos test.

        @param job: an Autotest job object.
        @param batch_size: an integer, max number of APs to lock in one batch.
        @param tries: an integer, number of iterations to run per AP.
        @param capturer_hostname: a string or None, hostname or IP of capturer.

        """

        lock_manager = host_lock_manager.HostLockManager()
        with host_lock_manager.HostsLockedBy(lock_manager):
            capture_host = self._allocate_packet_capturer(
                    lock_manager, hostname=capturer_hostname)
            capturer = site_linux_system.LinuxSystem(capture_host, {},
                                                     'packet_capturer')
            batch_locker = ap_batch_locker.ApBatchLocker(lock_manager,
                                                         self._ap_spec)
            while batch_locker.has_more_aps():
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
                        logging.error('The SSID was not set for the AP:%s', ap)

                    if not ap.get_configuration_success():
                        # The AP was not configured correctly
                        job.run_test('network_WiFi_ChaosConfigFailure',
                                     ap=ap,
                                     tag=ap.ssid)
                        continue
                    if not self.verify_bss_in_scan(ap.get_bss()):
                        # The BSS of the AP was not found
                        job.run_test('network_WiFi_ChaosConfigFailure',
                                     ap=ap,
                                     missing_from_scan=True,
                                     tag=ap.ssid)
                        continue

                    assoc_params = ap.get_association_parameters()

                    # TODO(wiley) We probably don't always want HT40, but
                    #             this information is hard to infer here.
                    #             Change how AP configuration happens so that
                    #             we expose this.
                    result = job.run_test(self._test,
                                 capturer=capturer,
                                 capturer_frequency=self._ap_spec.frequency,
                                 capturer_ht_type='HT40+',
                                 host=self._host,
                                 assoc_params=assoc_params,
                                 client=self._wifi_client,
                                 tries=tries,
                                 # Copy all logs from the system
                                 disabled_sysinfo=False,
                                 tag=ap.ssid)

                    logging.info('Test result: %d', result)

                    batch_locker.unlock_one_ap(ap.host_name)

                batch_locker.unlock_aps()
