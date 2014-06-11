# Copyright (c) 2014 The Chromium OS Authors. All rights reserved.
# Use of this source code is governed by a BSD-style license that can be
# found in the LICENSE file.

import contextlib
import datetime
import logging
import os
import pprint
import time
import re

from autotest_lib.client.common_lib.cros.network import chaos_constants
from autotest_lib.client.common_lib.cros.network import iw_runner
from autotest_lib.server import hosts
from autotest_lib.server import frontend
from autotest_lib.server import site_linux_system
from autotest_lib.server import site_utils
from autotest_lib.server.cros import host_lock_manager
from autotest_lib.server.cros.chaos_ap_configurators import ap_batch_locker
from autotest_lib.server.cros.chaos_ap_configurators import ap_configurator
from autotest_lib.server.cros.chaos_ap_configurators import ap_cartridge
from autotest_lib.server.cros.chaos_ap_configurators import ap_spec
from autotest_lib.server.cros.network import wifi_client


class ChaosRunner(object):
    """Object to run a network_WiFi_ChaosXXX test."""


    def __init__(self, test, host, spec, broken_pdus=list()):
        """Initializes and runs test.

        @param test: a string, test name.
        @param host: an Autotest host object, device under test.
        @param spec: an APSpec object.
        @param broken_pdus: list of offline PDUs.

        """
        self._test = test
        self._host = host
        self._ap_spec = spec
        self._broken_pdus = broken_pdus
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

        @return: An SSHHost object representing a locked packet_capture machine.
        """
        if hostname is not None:
            return hosts.SSHHost(hostname)

        afe = frontend.AFE(debug=True)
        return hosts.SSHHost(site_utils.lock_host_with_labels(
                afe, lock_manager, labels=['packet_capture']) + '.cros')


    def _power_down_aps(self, aps):
         """Powers down a list of aps.

         @param aps: a list of APConfigurator objects.

         """
         cartridge = ap_cartridge.APCartridge()
         for ap in aps:
             ap.power_down_router()
             cartridge.push_configurator(ap)
         cartridge.run_configurators(self._broken_pdus)


    def _configure_aps(self, aps):
        """Configures a given list of APs.

        @param aps: a list of APConfigurator objects.

        """
        cartridge = ap_cartridge.APCartridge()
        for ap in aps:
            ap.set_using_ap_spec(self._ap_spec)
            cartridge.push_configurator(ap)
        cartridge.run_configurators(self._broken_pdus)


    def _is_dut_healthy(self, client, ap):
        """Returns if iw scan is working properly.

        Sometimes iw scan will die, especially on the Atheros chips.
        This works around that bug.  See crbug.com/358716.

        @param client: a wifi_client for the DUT
        @param ap: ap_configurator object

        @returns True if the DUT is healthy (iw scan works); False otherwise.

        """
        # The SSID doesn't matter, all that needs to be verified is that iw
        # works.
        networks = client.iw_runner.wait_for_scan_result(client.wifi_if,
                                                         ssid=ap.ssid)
        if networks == None:
            return False
        return True


    def _is_conn_worker_healthy(self, conn_worker, ap, assoc_params, job):
        """Returns if the connection worker is working properly.

        From time to time the connection worker will fail to establish a
        connection to the APs.

        @param conn_worker: conn_worker object
        @param ap: an ap_configurator object
        @param assoc_params: the connection association parameters
        @param job: the Autotest job object

        @returns True if the worker is healthy; False otherwise

        """
        if conn_worker is None:
            return True

        conn_status = conn_worker.connect_work_client(assoc_params)
        if not conn_status:
            job.run_test('network_WiFi_ChaosConfigFailure', ap=ap,
                         error_string=chaos_constants.WORK_CLI_CONNECT_FAIL,
                         tag=ap.ssid)
            # Obtain the logs from the worker
            log_dir_name = str('worker_client_logs_%s' % ap.ssid)
            log_dir = os.path.join(job.resultdir, log_dir_name)
            conn_worker.host.collect_logs('/var/log', log_dir,
                                          ignore_errors=True)
            return False
        return True


    def _filter_quarantined_and_config_failed_aps(self, aps, batch_locker, job):
        """Filter out all PDU quarantined and config failed APs.

        @param aps: the list of ap_configurator objects to filter
        @param batch_locker: the batch_locker object
        @param job: an Autotest job object

        @returns a list of ap_configuration objects.

        """
        aps_to_remove = list()
        for ap in aps:
            failed_ap = False
            if ap.pdu in self._broken_pdus:
                ap.configuration_success = chaos_constants.PDU_FAIL

            if (ap.configuration_success == chaos_constants.PDU_FAIL):
                failed_ap = True
                error_string = chaos_constants.AP_PDU_DOWN
                tag = ap.host_name + '_PDU'
            elif (ap.configuration_success == chaos_constants.CONFIG_FAIL):
                failed_ap = True
                error_string = chaos_constants.AP_CONFIG_FAIL
                tag = ap.host_name

            if failed_ap:
                tag += '_' + str(int(round(time.time())))
                job.run_test('network_WiFi_ChaosConfigFailure',
                             ap=ap,
                             error_string=error_string,
                             tag=tag)
                aps_to_remove.append(ap)
                if error_string == chaos_constants.AP_CONFIG_FAIL:
                    self._release_ap(ap, batch_locker)
                else:
                    # Cannot use _release_ap, since power_down will fail
                    batch_locker.unlock_one_ap(ap.host_name)
        return list(set(aps) - set(aps_to_remove))


    def _get_security_from_scan(self, ap, networks, job):
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
            ap.configurator_type == ap_spec.CONFIGURATOR_STATIC):
            securities = [iw_runner.SECURITY_WPA, iw_runner.SECURITY_WPA2]
            # We have only seen WPA2 be backwards compatible, and we want
            # to verify the configurator did the right thing. So we
            # promote this to WPA2 only.
        elif (security == iw_runner.SECURITY_MIXED and
              ap.configurator_type == ap_spec.CONFIGURATOR_DYNAMIC):
            securities = [iw_runner.SECURITY_WPA2]
        else:
            securities = [security]
        return securities


    def _scan_for_networks(self, ssid, capturer):
        """Returns a list of matching networks after running iw scan.

        @param ssid: the SSID string to look for in scan.
        @param capturer: a packet capture device.

        @returns a list of the matching networks; if no networks are found at
                 all, returns None.

        """
        # Setup a managed interface to perform scanning on the
        # packet capture device.
        freq = ap_spec.FREQUENCY_TABLE[self._ap_spec.channel]
        wifi_if = capturer.get_wlanif(freq, 'managed')
        capturer.host.run('%s link set %s up' % (capturer.cmd_ip, wifi_if))

        # We have some APs that need a while to come on-line
        networks = capturer.iw_runner.wait_for_scan_result(wifi_if,
                                                           ssid=ssid,
                                                           timeout_seconds=300)
        capturer.remove_interface(wifi_if)
        return networks


    def _return_available_networks(self, ap, capturer, job):
        """Returns a list of networks configured as described by an APSpec.

        @param ap: the APConfigurator being testing against.
        @param capturer: a packet capture device
        @param job: an Autotest job object.

        @returns a list of networks returned from _scan_for_networks().

        """
        for i in range(2):
            networks = self._scan_for_networks(ap.ssid, capturer)
            if networks is None:
                return None
            if len(networks) == 0:
                # The SSID wasn't even found, abort
                logging.error('The ssid %s was not found in the scan', ap.ssid)
                job.run_test('network_WiFi_ChaosConfigFailure', ap=ap,
                             error_string=chaos_constants.AP_SSID_NOTFOUND,
                             tag=ap.ssid)
                return list()
            security = self._get_security_from_scan(ap, networks, job)
            if self._ap_spec.security in security:
                return networks
            if i == 0:
                # The SSID exists but the security is wrong, give the AP time
                # to possible update it.
                time.sleep(60)

        if self._ap_spec.security not in security:
            logging.error('%s was the expected security but got %s: %s',
                          self._ap_spec.security,
                          str(security).strip('[]'),
                          networks)
            job.run_test('network_WiFi_ChaosConfigFailure',
                         ap=ap,
                         error_string=chaos_constants.AP_SECURITY_MISMATCH,
                         tag=ap.ssid)
            networks = list()
        return networks


    def _release_ap(self, ap, batch_locker):
        """Powers down and unlocks the given AP.

        @param ap: the APConfigurator under test
        @param batch_locker: the batch locker object

        """
        ap.power_down_router()
        try:
            ap.apply_settings()
        except ap_configurator.PduNotResponding as e:
            if ap.pdu not in self._broken_pdus:
                self._broken_pdus.append(ap.pdu)
        batch_locker.unlock_one_ap(ap.host_name)


    def _sanitize_client(self):
        """Clean up logs and reboot the DUT."""
        self._host.run('rm -rf /var/log')
        self._host.reboot()


    def _get_firmware_ver(self):
        """Get firmware version of DUT from /var/log/messages.

        WiFi firmware version is matched against list of known firmware versions
        from ToT.

        @returns the WiFi firmware version as a string, None if the version
                 cannot be found.

        """

        # Firmware versions manually aggregated by installing ToT on each device
        known_firmware_ver = ['Atheros', 'mwifiex', 'loaded firmware version']

        # Find and return firmware version in logs
        for firmware_ver in known_firmware_ver:
            result_str = self._host.run('awk "/%s/ {print}" /var/log/messages'
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
                else:
                    logging.info('%s does not match known firmware versions.',
                                 result_str)
                    return None

                result = re.search(pattern, result_str)
                if result:
                    return result.group(0)

        return None


    def run(self, job, batch_size=15, tries=10, capturer_hostname=None,
            conn_worker=None, work_client_hostname=None,
            disabled_sysinfo=False):
        """Executes Chaos test.

        @param job: an Autotest job object.
        @param batch_size: an integer, max number of APs to lock in one batch.
        @param tries: an integer, number of iterations to run per AP.
        @param capturer_hostname: a string or None, hostname or IP of capturer.
        @param conn_worker: ConnectionWorkerAbstract or None, to run extra
                            work after successful connection.
        @param work_client_hostname: a string or None, hostname of work client
        @param disabled_sysinfo: a bool, disable collection of logs from DUT.

        """

        lock_manager = host_lock_manager.HostLockManager()
        with host_lock_manager.HostsLockedBy(lock_manager):
            capture_host = self._allocate_packet_capturer(
                    lock_manager, hostname=capturer_hostname)
            capturer = site_linux_system.LinuxSystem(capture_host, {},
                                                     'packet_capturer')
            if conn_worker is not None:
                work_client_machine = self._allocate_packet_capturer(
                        lock_manager, hostname=work_client_hostname)
                conn_worker.prepare_work_client(work_client_machine)
            batch_locker = ap_batch_locker.ApBatchLocker(lock_manager,
                                                         self._ap_spec)

            while batch_locker.has_more_aps():
                # Work around crbug.com/358716
                self._sanitize_client()
                healthy_dut = True
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

                    aps = self._filter_quarantined_and_config_failed_aps(aps,
                        batch_locker, job)

                    for ap in aps:
                        # http://crbug.com/306687
                        if ap.ssid == None:
                            logging.error('The SSID was not set for the AP:%s',
                                          ap)

                        healthy_dut = self._is_dut_healthy(client, ap)

                        if not healthy_dut:
                            logging.error('DUT is not healthy, rebooting.')
                            batch_locker.unlock_and_reclaim_aps()
                            break

                        networks = self._return_available_networks(ap,
                                                                   capturer,
                                                                   job)

                        if networks is None:
                            # If scan returned no networks, iw scan failed.
                            # Reboot the packet capturer device and
                            # reconfigure the capturer.
                            batch_locker.unlock_and_reclaim_ap(ap.host_name)
                            logging.error('Packet capture is not healthy, '
                                          'rebooting.')
                            capturer.host.reboot()
                            capturer = site_linux_system.LinuxSystem(
                                           capture_host, {},'packet_capturer')
                            continue
                        if networks == list():
                           # Packet capturer did not find the SSID in scan or
                           # there was a security mismatch.
                           self._release_ap(ap, batch_locker)
                           continue

                        assoc_params = ap.get_association_parameters()

                        if not self._is_conn_worker_healthy(conn_worker,
                                                            ap,
                                                            assoc_params,
                                                            job):
                            self._release_ap(ap, batch_locker)
                            continue

                        name = ap.name
                        kernel_ver = self._host.get_kernel_ver()
                        firmware_ver = self._get_firmware_ver()
                        if not firmware_ver:
                            firmware_ver = "Unknown"

                        debug_dict = {'ap_name': name,
                                      'kernel_version': kernel_ver,
                                      'wifi_firmware_version': firmware_ver}
                        debug_string = pprint.pformat(debug_dict)

                        result = job.run_test(self._test,
                                     capturer=capturer,
                                     capturer_frequency=networks[0].frequency,
                                     capturer_ht_type=networks[0].ht,
                                     host=self._host,
                                     assoc_params=assoc_params,
                                     client=client,
                                     tries=tries,
                                     debug_info=debug_string,
                                     # Copy all logs from the system
                                     disabled_sysinfo=disabled_sysinfo,
                                     conn_worker=conn_worker,
                                     tag=ap.ssid if conn_worker is None else
                                         '%s.%s' % (conn_worker.name, ap.ssid))

                        self._release_ap(ap, batch_locker)

                        if conn_worker is not None:
                            conn_worker.cleanup()

                    if not healthy_dut:
                        continue

                batch_locker.unlock_aps()
            capturer.close()
            if self._broken_pdus:
                logging.info('PDU is down!!!\nThe following PDUs are down:\n')
                pprint.pprint(self._broken_pdus)
