# Copyright (c) 2013 The Chromium OS Authors. All rights reserved.
# Use of this source code is governed by a BSD-style license that can be
# found in the LICENSE file.

import datetime
import logging
import random

from autotest_lib.client.common_lib import error
from autotest_lib.server import frontend
from autotest_lib.server import hosts
from autotest_lib.server import site_linux_system
from autotest_lib.server.cros import host_lock_manager
from autotest_lib.server.cros.chaos_ap_configurators import ap_batch_locker
from autotest_lib.server.cros.chaos_lib import chaos_base_test


class WifiChaosTest(object):
    """Helper object to set up and run Chaos test.

    @attribute test: a string, test name.
    @attribute host: an Autotest host object, device under test.
    @attribute ap_spec: a Python dictionary, desired attributes of Chaos APs.
    @attribute PSK_TEST: a string, name of Chaos PSK test.
    """
    PSK_TEST = 'network_WiFiChaosPSK'


    @staticmethod
    def allocate_packet_capturer(lock_manager, hostname):
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


    def __init__(self, test, host):
        """Initializes and runs test.

        @param test: a string, test name.
        @param host: an Autotest host object, device under test.
        """
        self._test = test
        self._host = host
        self._ap_spec = None
        # Log server and DUT times
        dt = datetime.datetime.now()
        logging.info('Server time: %s', dt.strftime('%a %b %d %H:%M:%S %Y'))
        logging.info('DUT time: %s', self._host.run('date').stdout.strip())


    def _setup(self, capturer):
        """Performs necessary setup before running Chaos test.

        @param capturer: a LinuxSystem object.
        @returns a WiFiChaosConnectionTest object.
        """
        helper = chaos_base_test.WiFiChaosConnectionTest(self._host, capturer)
        if self._test == self.PSK_TEST:
            logging.info('Perform additional setup for PSK test.')
            helper.psk_password = 'chromeos'
            psk_spec = {'securities': [helper.ap_config.SECURITY_TYPE_WPAPSK]}
            # Update ap_spec w/ PSK security
            self._ap_spec = dict(self._ap_spec.items() + psk_spec.items())

        return helper


    def run(self, job, ap_spec, batch_size, tries, capturer_hostname=None):
        """Executes Chaos test.

        @param job: an Autotest job object.
        @param ap_spec: a Python dictionary, desired attributes of Chaos APs.
        @param batch_size: an integer, max number of APs to lock in one batch.
        @param tries: an integer, number of iterations to run per AP.
        @param capturer_hostname: a string or None, hostname or IP of capturer.

        """
        self._ap_spec = ap_spec
        lock_manager = host_lock_manager.HostLockManager()
        with host_lock_manager.HostsLockedBy(lock_manager):
            capture_host = self.allocate_packet_capturer(
                    lock_manager, hostname=capturer_hostname)
            capturer = site_linux_system.LinuxSystem(capture_host, {},
                                                     'packet_capturer')
            helper = self._setup(capturer)
            batch_locker = ap_batch_locker.ApBatchLocker(lock_manager,
                                                         self._ap_spec)
            while batch_locker.has_more_aps():
                ap_batch = batch_locker.get_ap_batch(
                        batch_size=batch_size)
                if not ap_batch:
                    logging.info('No more APs to test.')
                    break

                # Power down all of the APs because some can get grumpy
                # if they are configured several times and remain on.
                helper.power_down_aps(ap_batch)
                security = ''
                if helper.psk_password != '':
                    security = helper.PSK

                # Test 2.4GHz band first, followed by 5GHz band. Release
                # APs as soon as we're done using them.
                aps_unlocked = set()
                for band in [helper.ap_config.BAND_2GHZ,
                             helper.ap_config.BAND_5GHZ]:

                    # Remove 2.4GHz-only APs before APs for 5GHz run
                    if band == helper.ap_config.BAND_5GHZ:
                        ap_batch = list(set(ap_batch) - aps_unlocked)

                    for ap_info in helper.config_aps(
                            ap_batch, band, security=security):
                        # Group test output by SSID
                        mod_ssid = ap_info['ssid'].replace(' ', '_')
                        job.run_test(self._test,
                                     host=self._host,
                                     helper=helper,
                                     ap_info=ap_info,
                                     tries=tries,
                                     disable_sysinfo=False,
                                     tag=mod_ssid)
                        if ap_info['ok_to_unlock']:
                            batch_locker.unlock_one_ap(
                                    ap_info['configurator'].host_name)
                            aps_unlocked.add(ap_info['configurator'])

                batch_locker.unlock_aps()
