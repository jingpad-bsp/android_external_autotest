# Copyright 2015 The Chromium OS Authors. All rights reserved.
# Use of this source code is governed by a BSD-style license that can be
# found in the LICENSE file.

import datetime
import logging
import os
import pprint
import time
import re
# hack(rpius)

from autotest_lib.client.common_lib import error
from autotest_lib.client.common_lib.cros.network import ap_constants
from autotest_lib.client.common_lib.cros.network import iw_runner
from autotest_lib.server import hosts
from autotest_lib.server import frontend
from autotest_lib.server import site_linux_system
from autotest_lib.server import site_utils
from autotest_lib.server.cros import host_lock_manager
from autotest_lib.server.cros.ap_configurators import ap_batch_locker
from autotest_lib.server.cros.ap_configurators import ap_configurator
from autotest_lib.server.cros.ap_configurators import ap_cartridge
from autotest_lib.server.cros.ap_configurators import ap_spec as ap_spec_module
from autotest_lib.server.cros.clique_lib import clique_dut_locker
from autotest_lib.server.cros.clique_lib import clique_dut_log_collector
from autotest_lib.server.cros.clique_lib import clique_dut_updater

class CliqueRunner(object):
    """Object to run a network_WiFi_CliqueXXX test."""


    def __init__(self, test, dut_pool_spec, ap_specs):
        """Initializes and runs test.

        @param test: a string, test name.
        @param dut_pool_spec: a list of pool sets. Each set contains a list of
                              board: <board_name> labels to chose the required
                              DUT's.
        @param ap_specs: a list of APSpec objects corresponding to the APs
                         needed for the test.
        """
        self._test = test
        self._ap_specs = ap_specs
        self._dut_pool_spec = dut_pool_spec
        self._dut_pool = []
        # Log server and DUT times
        dt = datetime.datetime.now()
        logging.info('Server time: %s', dt.strftime('%a %b %d %H:%M:%S %Y'))

    def _allocate_dut_pool(self, dut_locker):
        """Allocate the required DUT's from the spec for the test.
        The DUT objects are stored in a list of sets in |_dut_pool| attribute.

        @param dut_locker: DUTBatchLocker object used to allocate the DUTs
                           for the test pool.

        @return: Returns a list of DUTObjects allocated.
        """
        self._dut_pool  = dut_locker.get_dut_pool()
        # Flatten the list of DUT objects into a single list.
        dut_objects = sum(self._dut_pool, [])
        return dut_objects

    @staticmethod
    def _update_dut_pool(dut_objects, release_version):
        """Allocate the required DUT's from the spec for the test.

        @param dut_objects: A list of DUTObjects for all DUTs allocated for the
                            test.
        @param release_version: A chromeOS release version.

        @return: True if all the DUT's successfully upgraded, False otherwise.
        """
        dut_updater = clique_dut_updater.CliqueDUTUpdater()
        return dut_updater.update_dut_pool(dut_objects, release_version)

    @staticmethod
    def _collect_dut_pool_logs(dut_objects, job):
        """Allocate the required DUT's from the spec for the test.
        The DUT objects are stored in a list of sets in |_dut_pool| attribute.

        @param dut_objects: A list of DUTObjects for all DUTs allocated for the
                            test.
        @param job: Autotest job object to be used for log collection.

        @return: Returns a list of DUTObjects allocated.
        """
        log_collector = clique_dut_log_collector.CliqueDUTLogCollector()
        log_collector.collect_logs(dut_objects, job)

    @staticmethod
    def _allocate_packet_capturer(lock_manager, hostname):
        """Allocates a machine to capture packets.

        Locks the allocated machine if the machine was discovered via AFE
        to prevent tests stomping on each other.

        @param lock_manager HostLockManager object.
        @param hostname string optional hostname of a packet capture machine.

        @return: An SSHHost object representing a locked packet_capture machine.
        """
        if hostname is not None:
            return hosts.SSHHost(hostname)

        afe = frontend.AFE(debug=True, server='cautotest')
        return hosts.SSHHost(site_utils.lock_host_with_labels(
                afe, lock_manager, labels=['packet_capture']) + '.cros')

    @staticmethod
    def _is_dut_healthy(client, ap):
        """Returns if iw scan is working properly.

        Sometimes iw scan will die, especially on the Atheros chips.
        This works around that bug.  See crbug.com/358716.

        @param client: a wifi_client for the DUT
        @param ap: ap_configurator object

        @returns True if the DUT is healthy (iw scan works); False otherwise.
        """
        # The SSID doesn't matter, all that needs to be verified is that iw
        # works.
        networks = client.iw_runner.wait_for_scan_result(
                client.wifi_if, ssid=ap.ssid)
        if networks == None:
            return False
        return True

    def _are_all_duts_healthy(self, dut_objects, ap):
        """Returns if iw scan is not working on any of the DUTs.

        Sometimes iw scan will die, especially on the Atheros chips.
        This works around that bug.  See crbug.com/358716.

        @param dut_objects: A list of DUTObjects for all DUTs allocated for the
                            test.
        @param ap: ap_configurator object

        @returns True if all the DUTs are healthy, False otherwise.
        """
        healthy = True
        for dut in dut_objects:
            if not self._is_dut_healthy(dut.wifi_client, ap):
                logging.error('DUT %s not healthy.', dut.host.hostname)
                healthy = False
        return healthy

    @staticmethod
    def _sanitize_client(dut):
        """Clean up logs and reboot the DUT.

        @param dut: DUTObject corresponding to the DUT under test.
        """
        dut.host.run('rm -rf /var/log')
        dut.host.reboot()

    def _sanitize_all_clients(self, dut_objects):
        """Clean up logs and reboot all the DUTs.

        @param dut_objects: A list of DUTObjects for all DUTs allocated for the
                            test.
        """
        for dut in dut_objects:
            self._sanitize_client(dut)

    @staticmethod
    def _get_firmware_ver(dut):
        """Get firmware version of DUT from /var/log/messages.

        WiFi firmware version is matched against list of known firmware versions
        from ToT.

        @param dut: DUTObject corresponding to the DUT under test.

        @returns the WiFi firmware version as a string, None if the version
                 cannot be found.
        """
        # Firmware versions manually aggregated by installing ToT on each device
        known_firmware_ver = ['Atheros', 'mwifiex', 'loaded firmware version',
                              'brcmf_c_preinit_dcmds']
        # Find and return firmware version in logs
        for firmware_ver in known_firmware_ver:
            result_str = dut.run('awk "/%s/ {print}" /var/log/messages'
                                 % firmware_ver).stdout
            if not result_str:
                continue
            else:
                if 'Atheros' in result_str:
                    pattern = '%s \w+ Rev:\d' % firmware_ver
                elif 'mwifiex' in result_str:
                    pattern = '%s [\d.]+ \([\w.]+\)' % firmware_ver
                elif 'loaded firmware version' in result_str:
                    pattern = '(\d+\.\d+\.\d+.\d)'
                elif 'Firmware version' in result_str:
                    pattern = '\d+\.\d+\.\d+ \([\w.]+\)'
                else:
                    logging.info('%s does not match known firmware versions.',
                                 result_str)
                    return None

                result = re.search(pattern, result_str)
                if result:
                    return result.group(0)
        return None

    def _get_debug_string(self, dut_objects, aps):
        """Gets the debug info for all the DUT's and APs in the pool.

        This is printed in the logs at the end of each test scenario for
        debugging.
        @param dut_objects: A list of DUTObjects for all DUTs allocated for the
                            test.
        @param aps: A list of APConfigurator for all APs allocated for
                    the test.

        @returns a string with the list of information for each DUT and AP
                 in the pool.
        """
        debug_string = ""
        for dut in dut_objects:
            kernel_ver = dut.get_kernel_ver()
            firmware_ver = self._get_firmware_ver(dut)
            if not firmware_ver:
                firmware_ver = "Unknown"
            debug_dict = {'host_name': dut.host.hostname,
                          'kernel_versions': kernel_vers,
                          'wifi_firmware_versions': firmware_vers}
            debug_string += pprint.pformat(debug_dict)
        for ap in aps:
            debug_string += pprint.pformat({'ap_name': ap.name})
        return debug_string

    @staticmethod
    def _is_conn_worker_healthy(conn_worker, ap, assoc_params, job):
        """Returns if the connection worker is working properly.

        From time to time the connection worker will fail to establish a
        connection to the APs.

        @param conn_worker: conn_worker object.
        @param ap: an ap_configurator object.
        @param assoc_params: the connection association parameters.
        @param job: the Autotest job object.

        @returns True if the worker is healthy, False otherwise.
        """
        if conn_worker is None:
            return True

        conn_status = conn_worker.connect_work_client(assoc_params)
        if not conn_status:
            job.run_test('network_WiFi_CliqueConfigFailure', ap=ap,
                         error_string=ap_constants.WORK_CLI_CONNECT_FAIL,
                         tag=ap.ssid)
            # Obtain the logs from the worker
            log_dir_name = str('worker_client_logs_%s' % ap.ssid)
            log_dir = os.path.join(job.resultdir, log_dir_name)
            conn_worker.host.collect_logs('/var/log', log_dir,
                                          ignore_errors=True)
            return False
        return True

    def _are_conn_workers_healthy(self, workers, aps, assoc_params_list, job):
        """Returns if all the connection workers are working properly.

        From time to time the connection worker will fail to establish a
        connection to the APs.

        @param workers: a list of conn_worker objects.
        @param aps: a list of an ap_configurator objects.
        @param assoc_params_list: list of connection association parameters.
        @param job: the Autotest job object.

        @returns True if all the workers are healthy, False otherwise.
        """
        healthy = True
        for worker, ap, assoc_params in zip(workers, aps, assoc_params_list):
            if not self._is_conn_worker_healthy(worker, ap, assoc_params, job):
                logging.error('Connection worker %s not healthy.',
                              worker.host.hostname)
                healthy = False
        return healthy

    @staticmethod
    def _configure_aps(aps, ap_specs):
        """Configures a given list of APs.

        @param aps: a list of APConfigurator objects.
        @param ap_specs: a list of corresponding APSpec objects.
        """
        cartridge = ap_cartridge.APCartridge()
        for ap, ap_spec in zip(aps, ap_specs):
            ap.set_using_ap_spec(ap_spec)
            cartridge.push_configurator(ap)
        cartridge.run_configurators()

    @staticmethod
    def _get_security_from_scan(ap, networks, job):
        """Returns a list of securities determined from the scan result.

        @param ap: the APConfigurator being testing against.
        @param networks: List of matching networks returned from scan.
        @param job: an Autotest job object

        @returns a list of possible securities for the given network.
        """
        securities = list()
        # Sanitize MIXED security setting for both Static and Dynamic
        # configurators before doing the comparison.
        security = networks[0].security
        if (security == iw_runner.SECURITY_MIXED and
            ap.configurator_type == ap_spec_module.CONFIGURATOR_STATIC):
            securities = [iw_runner.SECURITY_WPA, iw_runner.SECURITY_WPA2]
            # We have only seen WPA2 be backwards compatible, and we want
            # to verify the configurator did the right thing. So we
            # promote this to WPA2 only.
        elif (security == iw_runner.SECURITY_MIXED and
              ap.configurator_type == ap_spec_module.CONFIGURATOR_DYNAMIC):
            securities = [iw_runner.SECURITY_WPA2]
        else:
            securities = [security]
        return securities

    @staticmethod
    def _scan_for_networks(ssid, ap_spec, capturer):
        """Returns a list of matching networks after running iw scan.

        @param ssid: the SSID string to look for in scan.
        @param ap_spec: AP spec object corresponding to the AP.
        @param capturer: a packet capture device.

        @returns a list of the matching networks; if no networks are found at
                 all, returns None.
        """
        # Setup a managed interface to perform scanning on the
        # packet capture device.
        freq = ap_spec_module.FREQUENCY_TABLE[ap_spec.channel]
        wifi_if = capturer.get_wlanif(freq, 'managed')
        capturer.host.run('%s link set %s up' % (capturer.cmd_ip, wifi_if))

        # We have some APs that need a while to come on-line
        networks = capturer.iw_runner.wait_for_scan_result(
                wifi_if, ssid=ssid, timeout_seconds=300)
        capturer.remove_interface(wifi_if)
        return networks

    def _return_available_networks(self, ap, ap_spec, capturer, job):
        """Returns a list of networks configured as described by an APSpec.

        @param ap: the APConfigurator being testing against.
        @param ap_spec: AP spec object corresponding to the AP.
        @param capturer: a packet capture device
        @param job: an Autotest job object.

        @returns a list of networks returned from _scan_for_networks().
        """
        for i in range(2):
            networks = self._scan_for_networks(ap.ssid, ap_spec, capturer)
            if networks is None:
                return None
            if len(networks) == 0:
                # The SSID wasn't even found, abort
                logging.error('The ssid %s was not found in the scan', ap.ssid)
                job.run_test('network_WiFi_ChaosConfigFailure',
                             ap=ap,
                             error_string=ap_constants.AP_SSID_NOTFOUND,
                             tag=ap.ssid)
                return list()
            security = self._get_security_from_scan(ap, networks, job)
            if self._ap_spec.security in security:
                return networks
            if i == 0:
                # The SSID exists but the security is wrong, give the AP time
                # to possible update it.
                time.sleep(60)

        if ap_spec.security not in security:
            logging.error('%s was the expected security but got %s: %s',
                          ap_spec.security,
                          str(security).strip('[]'),
                          networks)
            job.run_test('network_WiFi_ChaosConfigFailure',
                         ap=ap,
                         error_string=ap_constants.AP_SECURITY_MISMATCH,
                         tag=ap.ssid)
            networks = list()
        return networks

    def _cleanup(self, dut_objects, dut_locker, ap_locker, capturer,
                 conn_workers):
        """Cleans up after the test is complete.

        @param dut_objects: A list of DUTObjects for all DUTs allocated for the
                            test.
        @param dut_locker: DUTBatchLocker object used to allocate the DUTs
                           for the test pool.
        @param ap_locker: the AP batch locker object.
        @param capturer: a packet capture device.
        @param conn_workers: a list of conn_worker objects.
        """
        self._collect_dut_pool_logs(dut_objects)
        for worker in conn_workers:
            if worker: worker.cleanup()
        capturer.close()
        ap_locker.unlock_aps()
        dut_locker.unlock_and_close_duts()

    def run(self, job, tries=10, capturer_hostname=None, conn_workers=[],
            conn_worker_hostnames=[], release_version="",
            disabled_sysinfo=False):
        """Executes Clique test.

        @param job: an Autotest job object.
        @param tries: an integer, number of iterations to run per AP.
        @param capturer_hostname: a string or None, hostname or IP of capturer.
        @param conn_workers: List of ConnectionWorkerAbstract objects, to
                             run extra work after successful connection.
        @param conn_worker_hostnames: a list of string, hostname of
                                      connection workers.
        @param release_version: the DUT cros image version to use for testing.
        @param disabled_sysinfo: a bool, disable collection of logs from DUT.
        """
        lock_manager = host_lock_manager.HostLockManager()
        with host_lock_manager.HostsLockedBy(lock_manager):
            dut_locker = clique_dut_locker.CliqueDUTBatchLocker(
                    lock_manager, self._dut_pool_spec)
            dut_objects = self._allocate_dut_pool(dut_locker)
            if not dut_objects:
                raise error.TestError('No DUTs allocated for test.')
            update_status = self._update_dut_pool(dut_objects, release_version)
            if not update_status:
                raise error.TestError('DUT pool update failed. Bailing!')

            capture_host = self._allocate_packet_capturer(
                    lock_manager, hostname=capturer_hostname)
            capturer = site_linux_system.LinuxSystem(
                    capture_host, {}, 'packet_capturer')
            for worker, hostname in zip(conn_workers, conn_worker_hostnames):
                if worker:
                    work_client = self._allocate_packet_capturer(
                            lock_manager, hostname=hostname)
                    worker.prepare_work_client(work_client)

            aps = []
            for ap_spec in self._ap_specs:
                ap_locker = ap_batch_locker.ApBatchLocker(
                        lock_manager, ap_spec,
                        ap_test_type=ap_constants.AP_TEST_TYPE_CLIQUE)
                ap = ap_locker.get_ap_batch(batch_size=1)
                if not ap:
                    raise error.TestError('AP matching spec not found.')
                aps.append(ap)

            # Reset all the DUTs before the test starts and configure all the
            # APs.
            self._sanitize_all_clients(dut_objects)
            self._configure_aps(aps, self._ap_specs)

            # This is a list of association parameters for the test for all the
            # APs in the test.
            assoc_params_list = []
            # Check if all our APs, DUTs and connection workers are in good
            # state before we proceed.
            for ap, ap_spec in zip(aps, self._ap_specs):
                if ap.ssid == None:
                    self._cleanup(dut_objects, dut_locker, ap_locker,
                                  capturer, conn_workers)
                    raise error.TestError('SSID not set for the AP: %s.' %
                                          ap.configurator.host_name)
                networks = self._return_available_networks(
                        ap, ap_spec, capturer, job)
                if ((networks is None) or (networks == list())):
                    self._cleanup(dut_objects, dut_locker, ap_locker,
                                  capturer, conn_workers)
                    raise error.TestError('Scanning error on the AP %s.' %
                                          ap.configurator.host_name)

                assoc_params = ap.get_association_parameters()
                assoc_params_list.append(assoc_params)

            if not self._are_all_duts_healthy(dut_objects, ap):
                self._cleanup(dut_objects, dut_locker, ap_locker,
                              capturer, conn_workers)
                raise error.TestError('Not all DUTs healthy.')

            if not self._are_conn_workers_healthy(
                    conn_workers, aps, assoc_params_list, job):
                self._cleanup(dut_objects, dut_locker, ap_locker,
                              capturer, conn_workers)
                raise error.TestError('Not all connection workers healthy.')

            debug_string = self._get_debug_string(dut_objects, aps)

            result = job.run_test(
                    self._test,
                    capturer=capturer,
                    capturer_frequency=networks[0].frequency,
                    capturer_ht_type=networks[0].ht,
                    dut_pool=self._dut_pool,
                    assoc_params_list=assoc_params_list,
                    tries=tries,
                    debug_info=debug_string,
                    # Copy all logs from the system
                    disabled_sysinfo=disabled_sysinfo,
                    conn_workers=conn_workers)

            # Reclaim all the APs, DUTs and capturers used in the test and
            # collect the required logs.
            self._cleanup(dut_objects, dut_locker, ap_locker,
                          capturer, conn_workers)
