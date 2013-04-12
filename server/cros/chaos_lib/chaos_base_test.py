# Copyright (c) 2013 The Chromium OS Authors. All rights reserved.
# Use of this source code is governed by a BSD-style license that can be
# found in the LICENSE file.

import logging
import os
import pprint

from datetime import datetime

from autotest_lib.client.common_lib import error
from autotest_lib.server.cros.chaos_ap_configurators import ap_cartridge
from autotest_lib.server.cros.chaos_ap_configurators import ap_configurator
from autotest_lib.server.cros.chaos_ap_configurators import \
    ap_configurator_factory
from autotest_lib.server.cros.chaos_ap_configurators import \
    download_chromium_prebuilt
from autotest_lib.server.cros.chaos_config import ChaosAP
from autotest_lib.server.cros.wlan import connector, disconnector
from autotest_lib.server.cros.wlan import profile_manager


class WiFiChaosConnectionTest(object):
    """Base class for simple (connect/disconnect) dynamic Chaos test.

    @attribute host: an Autotest host object, DUT.
    @attribute connector: a TracingConnector object.
    @attribute disconnector: a Disconnector object.
    @attribute error_list: a list of errors, intermediate test failures.
    @attribute generic_ap: a generic APConfigurator object.
    @attribute factory: an APConfiguratorFactory object.
    @attribute psk_password: a string, password used for PSK authentication.

    @attribute LOG_FILES: a string, log files to record per-run data.
    @attribute PSK: a string, WiFi Pre-Shared Key (Personal) mode.
    """

    LOG_FILES = ({'file': '/var/log/messages'}, {'file': '/var/log/net.log'})
    PSK = 'psk'


    def __init__(self, host, capturer):
        """Initialize.

        @param host: an Autotest host object, device under test (DUT).
        @param capturer: a PacketCaptureManager object, packet tracer.
        """
        self.host = host
        self.connector = connector.TracingConnector(self.host, capturer)
        self.disconnector = disconnector.Disconnector(self.host)
        self.error_list = []
        self.generic_ap = ap_configurator.APConfigurator()
        self.factory = ap_configurator_factory.APConfiguratorFactory()
        self.psk_password = ''


    def _mark_line_count(self, logs, key):
        """Records line count as key in logs.

        @param logs: a tuple of dicts containing log file attributes.
        @param key: a string, name of a key to add to logs.

        @returns an updated dictionary with the key and line count.
        """
        for log in logs:
            command = "wc -l %s | awk '{print $1}'" % log['file']
            log[key] = int(self.host.run(command).stdout.strip())
        return logs


    # TODO(krisr): utilize incremental logging provided by lab team
    def _log_to_files(self, logs, log_dir, iteration):
        """Log run-specific data to LOG_FILES.

        @param logs: a dict containing log file attributes.
        @param log_dir: a string, directory to store test output.
        @param iteration: an integer, current iteration (1-indexed).
        """
        logs = self._mark_line_count(logs, 'end')
        for log in logs:
            line_count = log['end'] - log['start']
            cmd = 'tail -n %d %s' % (line_count, log['file'])
            output = self.host.run(cmd).stdout
            file_path = os.path.join(log_dir, os.path.basename(log['file']))
            file_path += '_%d' % iteration
            with open(file_path, 'w') as f:
                f.write(output)


    def run_connect_disconnect_test(self, ap_info):
        """Attempts to connect to an AP.

        @param ap_info: a dict of attributes of a specific AP.

        @return a string (error message) or None.
        """
        self.disconnector.disconnect(ap_info['ssid'])
        self.connector.set_frequency(ap_info['frequency'])

        # Use profile manager to prevent fallback connections.
        with profile_manager.ProfileManager(self.host) as pm:
            try:
                self.connector.connect(
                    ap_info['ssid'],
                    security=ap_info.get('security', ''),
                    psk=ap_info.get(self.PSK, ''),
                    frequency=ap_info['frequency'])
            except (connector.ConnectException,
                    connector.ConnectFailed,
                    connector.ConnectTimeout) as e:
                error = str(e)
                logging.error(error)
                return error
            finally:
                self.disconnector.disconnect(ap_info['ssid'])


    def run_ap_test(self, ap_info, tries, log_dir):
        """Runs test on a configured AP.

        @param ap_info: a dict of attributes of a specific AP.
        @param tries: an integer, number of connection attempts.
        @param log_dir: a string, directory to store test logs.
        """
        ap_info['failed_iterations'] = []
        # Make iteration 1-indexed
        for iteration in range(1, tries+1):
            logging.info('Connection try %d', iteration)
            filename = os.path.join(log_dir,
                                    'connect_try_%d' % iteration)
            self.connector.set_filename(filename)

            logs = self._mark_line_count(self.LOG_FILES, 'start')
            resp = self.run_connect_disconnect_test(ap_info)
            if resp:
                ap_info['failed_iterations'].append({'error': resp,
                                                     'try': iteration})
            self._log_to_files(logs, log_dir, iteration)

        if ap_info['failed_iterations']:
            self.error_list.append(ap_info)


    def _config_one_ap(self, ap, band, channel, security, mode):
        """Configures an AP for the test.

        @param ap: an APConfigurator object.
        @param band: a string, 2.4GHz or 5GHz.
        @param channel: an integer.
        @param security: a string, AP security method.
        @param mode: a hexadecimal, 802.11 mode.

        @returns a dict representing one band of a configured AP.
        """
        # Setting the band gets you the bss
        ap.set_band(band)
        ssid = '_'.join([ap.get_router_short_name(),
                         str(channel),
                         str(band).replace('.', '_')])

        ap.power_up_router()
        ap.set_channel(channel)
        ap.set_radio(enabled=True)
        ap.set_ssid(ssid)
        ap.set_visibility(visible=True)

        ap.set_mode(mode)
        if security == self.PSK:
            ap.set_security_wpapsk(self.psk_password)
        else:  # Testing open system, i.e. security = ''
            ap.set_security_disabled()

        # DO NOT apply_settings() here. Cartridge is used to apply config
        # settings to multiple APs in parallel, see config_aps().

        return {
            'configurator': ap,
            'bss': ap.get_bss(),
            'band': band,
            'channel': channel,
            'frequency': ChaosAP.FREQUENCY_TABLE[channel],
            'radio': True,
            'ssid': ssid,
            'visibility': True,
            'security': security,
            self.PSK: self.psk_password,
            'brand': ap.config_data.get_brand(),
            'model': ap.get_router_short_name(),
            }


    def _get_mode_type(self, ap, band):
        """Gets 802.11 mode for ap at band.

        @param ap: an APConfigurator object.
        @param band: a string, 2.4GHz or 5GHz.

        @returns a hexadecimal, 802.11 mode or None.
        """
        for mode in ap.get_supported_modes():
            if mode['band'] == band:
                for mode_type in mode['modes']:
                    if (mode_type & self.generic_ap.mode_n !=
                        self.generic_ap.mode_n):
                        return mode_type


    def config_aps(self, aps, band, channel, security=''):
        """Configures a list of APs.

        @param aps: a list of APConfigurator objects.
        @param band: a string, 2.4GHz or 5GHz.
        @param channel: an integer.
        @param security: a string, AP security method. Defaults to empty string
                         (i.e. open system). Other possible value is self.PSK.

        @returns a list of dicts, each a return by _config_one_ap().
        """
        configured_aps = []
        cartridge = ap_cartridge.APCartridge()
        for ap in aps:
            logging.info('Configuring AP %s', ap.get_router_name())
            if not ap.is_band_and_channel_supported(band, channel):
                continue

            mode = self._get_mode_type(ap, band)
            ap_info = self._config_one_ap(ap, band, channel, security, mode)
            configured_aps.append(ap_info)
            cartridge.push_configurator(ap)

        # Apply config settings to multiple APs in parallel.
        cartridge.run_configurators()
        return configured_aps


    def get_bands_and_channels(self):
        """Returns band and channel config for a generic dual-band AP.

        Test on channel 5 for 2.4GHz band and channel 48 for 5GHz band.

        @returns a list of tuples, (band, channel).
        """
        # Log server and DUT times
        dt = datetime.now()
        logging.info('Server time: %s', dt.strftime('%a %b %d %H:%M:%S %Y'))
        logging.info('DUT time: %s', self.host.run('date').stdout.strip())

        bands = [self.generic_ap.band_2ghz, self.generic_ap.band_5ghz]
        # TODO(tgao): support passing in channel params someday?
        channels = [5, 48]

        return zip(bands, channels)


    def check_webdriver_available(self):
        """Verifies webdriver binary is installed and running.

        Webdriver binary must be started manually from outside chroot.

        @raises TestError: if failed to download and install webdriver binary.
        """
        try:
            download_chromium_prebuilt.download_chromium_prebuilt_binaries()
        except IOError as e:
            err = ('Download failed: %s. Once resolved, from outside chroot, '
                   'run: <path to chroot directory>%s/chromedriver' %
                   (e, download_chromium_prebuilt.DOWNLOAD_PATH))
            raise error.TestError(err)


    def power_down(self, ap):
        """Powers down ap.

        @param ap: an APConfigurator object.
        """
        ap.power_down_router()
        ap.apply_settings()


    def power_down_aps(self, aps):
        """Powers down a list of aps.

        @param aps: a list of APConfigurator objects.
        """
        cartridge = ap_cartridge.APCartridge()
        for ap in aps:
            ap.power_down_router()
            cartridge.push_configurator(ap)
        cartridge.run_configurators()


    def check_test_error(self):
        """Checks if any intermediate test failed.

        @raises TestFail: if self.error_list is not empty.
        """
        if self.error_list:
            msg = '\nFailed with the following errors:\n'
            msg += pprint.pformat(self.error_list)
            # This is shared across tests; reset for the next AP.
            self.error_list = []
            raise error.TestFail(msg)


    def run_once(self, tries=1):
        """Main entry function for autotest.

        @param tries: an integer, number of connection attempts.
        """
        raise NotImplementedError('Child class must implement this!')
