# Copyright (c) 2012 The Chromium Authors. All rights reserved.
# Use of this source code is governed by a BSD-style license that can be
# found in the LICENSE file.

"""File containing class to build all available ap_configurators."""

import logging

from autotest_lib.client.common_lib import global_config
from autotest_lib.server.cros import chaos_config
from autotest_lib.server.cros.chaos_ap_configurators import ap_cartridge
from autotest_lib.server.cros.chaos_ap_configurators import ap_spec
from autotest_lib.server.cros.dynamic_suite import frontend_wrappers

CONFIG = global_config.global_config

_DEFAULT_AUTOTEST_INSTANCE = CONFIG.get_config_value('SERVER', 'hostname',
                                                     type=str)

class APConfiguratorFactory(object):
    """Class that instantiates all available APConfigurators.

    @attribute CONFIGURATOR_MAP: a dict of strings, mapping to model-specific
                                 APConfigurator objects.
    @attribute BANDS: a string, bands supported by an AP.
    @attribute MODES: a string, 802.11 modes supported by an AP.
    @attribute SECURITIES: a string, security methods supported by an AP.
    @attribute HOSTNAMES: a string, AP hostname.
    @attribute ap_list: a list of APConfigurator objects.
    @attribute ap_config: an APConfiguratorConfig object.
    """

    PREFIX='autotest_lib.server.cros.chaos_ap_configurators.'
    CONFIGURATOR_MAP = {
        'LinksysAPConfigurator':
            [PREFIX + 'linksys_ap_configurator',
                'LinksysAPConfigurator'],
        'LinksysAP15Configurator':
            [PREFIX + 'linksys_ap_15_configurator',
                'LinksysAP15Configurator'],
        'DLinkAPConfigurator':
            [PREFIX + 'dlink_ap_configurator',
                'DLinkAPConfigurator'],
        'TrendnetAPConfigurator':
            [PREFIX + 'trendnet_ap_configurator',
                'TrendnetAPConfigurator'],
        'Trendnet691grAPConfigurator':
            [PREFIX + 'trendnet691gr_ap_configurator',
                'Trendnet691grAPConfigurator'],
        'Trendnet731brAPConfigurator':
            [PREFIX + 'trendnet731br_ap_configurator',
                'Trendnet731brAPConfigurator'],
        'Trendnet432brpAPConfigurator':
            [PREFIX + 'trendnet432brp_ap_configurator',
                'Trendnet432brpAPConfigurator'],
        'Trendnet692grAPConfigurator':
            [PREFIX + 'trendnet692gr_ap_configurator',
                'Trendnet692grAPConfigurator'],
        'Trendnet654trAPConfigurator':
            [PREFIX + 'trendnet654tr_ap_configurator',
                'Trendnet654trAPConfigurator'],
        'Trendnet812druAPConfigurator':
            [PREFIX + 'trendnet812dru_ap_configurator',
                'Trendnet812druAPConfigurator'],
        'DLinkDIR655APConfigurator':
            [PREFIX + 'dlink_dir655_ap_configurator',
                'DLinkDIR655APConfigurator'],
        'BuffaloAPConfigurator':
            [PREFIX + 'buffalo_ap_configurator',
                'BuffaloAPConfigurator'],
        'BuffalowzrAPConfigurator':
            [PREFIX + 'buffalo_wzr_d1800h_ap_configurator',
                'BuffalowzrAPConfigurator'],
        'AsusAPConfigurator':
            [PREFIX + 'asus_ap_configurator',
                'AsusAPConfigurator'],
        'AsusQISAPConfigurator':
            [PREFIX + 'asus_qis_ap_configurator',
                'AsusQISAPConfigurator'],
        'Asus66RAPConfigurator':
            [PREFIX + 'asus_ac66r_ap_configurator',
                'Asus66RAPConfigurator'],
        'Netgear3700APConfigurator':
            [PREFIX + 'netgear3700_ap_configurator',
                'Netgear3700APConfigurator'],
        'NetgearR6200APConfigurator':
            [PREFIX + 'netgearR6200_ap_configurator',
                'NetgearR6200APConfigurator'],
        'Netgear1000APConfigurator':
            [PREFIX + 'netgear1000_ap_configurator',
                'Netgear1000APConfigurator'],
        'Netgear2000APConfigurator':
            [PREFIX + 'netgear2000_ap_configurator',
                'Netgear2000APConfigurator'],
        'Netgear4300APConfigurator':
            [PREFIX + 'netgear4300_ap_configurator',
                'Netgear4300APConfigurator'],
        'Netgear4500APConfigurator':
            [PREFIX + 'netgear4500_ap_configurator',
                'Netgear4500APConfigurator'],
        'LinksyseDualBandAPConfigurator':
            [PREFIX + 'linksyse_dual_band_configurator',
                'LinksyseDualBandAPConfigurator'],
        'Linksyse2000APConfigurator':
            [PREFIX + 'linksyse2000_ap_configurator',
                'Linksyse2000APConfigurator'],
        'NetgearDualBandAPConfigurator':
            [PREFIX + 'netgear_WNDR_dual_band_configurator',
                'NetgearDualBandAPConfigurator'],
        'BelkinAPConfigurator':
            [PREFIX + 'belkin_ap_configurator',
                'BelkinAPConfigurator'],
        'BelkinF5D7234APConfigurator':
            [PREFIX + 'belkinF5D7234_ap_configurator',
                'BelkinF5D7234APConfigurator'],
        'BelkinF5D8236APConfigurator':
            [PREFIX + 'belkinF5D8236_ap_configurator',
                'BelkinF5D8236APConfigurator'],
        'BelkinF6D4230APConfigurator':
            [PREFIX + 'belkinF6D4230_ap_configurator',
                'BelkinF6D4230APConfigurator'],
        'BelkinF7DAPConfigurator':
            [PREFIX + 'belkinF7D_ap_configurator',
                'BelkinF7DAPConfigurator'],
        'BelkinF7D1301APConfigurator':
            [PREFIX + 'belkinF7D1301_ap_configurator',
                'BelkinF7D1301APConfigurator'],
        'BelkinF9KAPConfigurator':
            [PREFIX + 'belkinF9K_ap_configurator',
                'BelkinF9KAPConfigurator'],
        'BelkinF9K1001APConfigurator':
            [PREFIX + 'belkinF9K1001_ap_configurator',
                'BelkinF9K1001APConfigurator'],
        'BelkinF9K1102APConfigurator':
            [PREFIX + 'belkinF9K1102_ap_configurator',
                'BelkinF9K1102APConfigurator'],
        'BelkinF9K1103APConfigurator':
            [PREFIX + 'belkinF9K1103_ap_configurator',
                'BelkinF9K1103APConfigurator'],
        'BelkinF9K1105APConfigurator':
            [PREFIX + 'belkinF9K1105_ap_configurator',
                'BelkinF9K1105APConfigurator'],
        'BelkinWRTRAPConfigurator':
            [PREFIX + 'belkinWRTR_ap_configurator',
                'BelkinWRTRAPConfigurator'],
        'MediaLinkAPConfigurator':
            [PREFIX + 'medialink_ap_configurator',
                'MediaLinkAPConfigurator'],
        'NetgearSingleBandAPConfigurator':
            [PREFIX + 'netgear_single_band_configurator',
                'NetgearSingleBandAPConfigurator'],
        'DLinkwbr1310APConfigurator':
            [PREFIX + 'dlinkwbr1310_ap_configurator',
                'DLinkwbr1310APConfigurator'],
        'Linksyse2100APConfigurator':
            [PREFIX + 'linksyse2100_ap_configurator',
                'Linksyse2100APConfigurator'],
        'LinksyseSingleBandAPConfigurator':
            [PREFIX + 'linksyse_single_band_configurator',
                'LinksyseSingleBandAPConfigurator'],
        'Linksyse2500APConfigurator':
            [PREFIX + 'linksyse2500_ap_configurator',
                'Linksyse2500APConfigurator'],
        'WesternDigitalN600APConfigurator':
            [PREFIX + 'westerndigitaln600_ap_configurator',
                'WesternDigitalN600APConfigurator'],
        'Linksyse1000APConfigurator':
            [PREFIX + 'linksyse1000_ap_configurator',
                'Linksyse1000APConfigurator'],
        'LinksysWRT160APConfigurator':
            [PREFIX + 'linksyswrt160_ap_configurator',
                'LinksysWRT160APConfigurator'],
        'Keeboxw150nrAPConfigurator':
            [PREFIX + 'keeboxw150nr_ap_configurator',
                'Keeboxw150nrAPConfigurator'],
        'EdimaxAPConfigurator':
            [PREFIX + 'edimax_ap_configurator',
                'EdimaxAPConfigurator'],
        'Edimax6475ndAPConfigurator':
            [PREFIX + 'edimax6475nd_ap_configurator',
                'Edimax6475ndAPConfigurator'],
        'StaticAPConfigurator':
            [PREFIX + 'static_ap_configurator',
                'StaticAPConfigurator'],
    }

    BANDS = 'bands'
    MODES = 'modes'
    SECURITIES = 'securities'
    HOSTNAMES = 'hostnames'


    def __init__(self):
        webdriver_ready = False
        self.ap_list = []
        for ap in chaos_config.get_ap_list():
            module_name, configurator_class = \
                    self.CONFIGURATOR_MAP[ap.get_class()]
            module = __import__(module_name, fromlist=configurator_class)
            configurator = module.__dict__[configurator_class]
            # NOTE: Using configurator.webdriver_port() existance to determine
            #       if this configurator needs access to webdriver.  The goal
            #       is to avoid 'import'ing webdriver if the available
            #       configurators do not require it (ie. StaticAPConfigurator).
            if not webdriver_ready and hasattr(configurator, 'webdriver_port'):
                from autotest_lib.server.cros.chaos_ap_configurators import \
                    download_chromium_prebuilt
                download_chromium_prebuilt.check_webdriver_ready()
                webdriver_ready = True

            self.ap_list.append(configurator(ap_config=ap))


    def _get_aps_by_visibility(self, visible=True):
        """Returns all configurators that support setting visibility.

        @param visibility = True if SSID should be visible; False otherwise.

        @returns aps: a set of APConfigurators"""
        if visible:
            return set(self.ap_list)

        return set(filter(lambda ap: ap.is_visibility_supported(),
                          self.ap_list))


    def _get_aps_by_mode(self, band, mode):
        """Returns all configurators that support a given 802.11 mode.

        @param band: an 802.11 band.
        @param mode: an 802.11 modes.

        @returns aps: a set of APConfigurators.
        """
        if not mode:
            return set(self.ap_list)

        aps = []
        for ap in self.ap_list:
            modes = ap.get_supported_modes()
            for d in modes:
                if d['band'] == band and mode in d['modes']:
                    aps.append(ap)
        return set(aps)


    def _get_aps_by_security(self, security):
        """Returns all configurators that support a given security mode.

        @param security: the security type

        @returns aps: a set of APConfigurators.
        """

        if not security:
            return set(self.ap_list)

        aps = []
        for ap in self.ap_list:
            if ap.is_security_mode_supported(security):
                aps.append(ap)
        return set(aps)


    def _get_aps_by_band(self, band, channel=None):
        """Returns all APs that support a given band.

        @param band: the band desired.

        @returns aps: a set of APConfigurators.
        """
        if not band:
            return set(self.ap_list)

        aps = []
        for ap in self.ap_list:
            bands_and_channels = ap.get_supported_bands()
            for d in bands_and_channels:
                if channel:
                    if d['band'] == band and channel in d['channels']:
                        aps.append(ap)
                elif d['band'] == band:
                    aps.append(ap)
        return set(aps)


    def get_aps_by_hostnames(self, hostnames, ap_list=None):
        """Returns specific APs by host name.

        @param hostnames: a list of strings, AP's wan_hostname defined in
                          ../chaos_dynamic_ap_list.conf.
        @param ap_list: a list of APConfigurator objects.

        @return a list of APConfigurators.
        """
        if ap_list == None:
            ap_list = self.ap_list

        aps = []
        for ap in ap_list:
            if ap.host_name in hostnames:
                logging.info('Found AP by hostname %s', ap.host_name)
                aps.append(ap)

        return aps


    def _get_aps_by_configurator_type(self, configurator_type, ap_list):
        """Returns APs that match the given configurator type.

        @param configurator_type: the type of configurtor to return.

        @return a list of APConfigurators.
        """
        aps = []
        for ap in ap_list:
            if ap.configurator_type == configurator_type:
                aps.append(ap)

        return aps


    def _get_aps_by_lab_location(self, want_chaos_aps, ap_list):
        """Returns APs that are inside or outside of the chaos lab.

        @param want_chaos_aps: True to select only APs in the chaos chamber.
                               False to select APs outside of the chaos chamber.

        @return a list of APConfigurators
        """
        aps = []
        afe = frontend_wrappers.RetryingAFE(server=_DEFAULT_AUTOTEST_INSTANCE,
                                            timeout_min=10,
                                            delay_sec=5)
        all_aps = set(afe.get_hostnames(label='chaos_ap'))
        chaos_devices = set(afe.get_hostnames(label='chaos_chamber'))
        chaos_aps = all_aps.intersection(chaos_devices)
        for ap in ap_list:
            if want_chaos_aps and ap.host_name in chaos_aps:
                aps.append(ap)

            if not want_chaos_aps and ap.host_name not in chaos_aps:
                aps.append(ap)

        return aps


    def get_ap_configurators_by_spec(self, spec=None, pre_configure=False):
        """Returns available configurators meeting spec.

        @param spec: a validated ap_spec object
        @param pre_configure: boolean, True to set all of the configuration
                              options for the APConfigurator object using the
                              given ap_spec; False otherwise.  An ap_spec must
                              be passed for this to have any effect.
        @returns aps: a list of APConfigurator objects
        """
        if not spec:
            return self.ap_list

        def _get_unique_aps(existing_aps, new_aps):
            """ Creates and returns a set of aps.

            @param existing_aps: Existing set of aps.
            @param new_aps: Set of aps to be added to the existing set.

            @return a new set of aps.
            """
            if new_aps:
                if existing_aps:
                    existing_aps &= new_aps
                else:
                    existing_aps = new_aps
            return existing_aps

        aps = set()
        aps = _get_unique_aps(aps, self._get_aps_by_band(spec.band,
                                                 channel=spec.channel))
        aps = _get_unique_aps(aps, self._get_aps_by_mode(spec.band, spec.mode))
        aps = _get_unique_aps(aps, self._get_aps_by_security(spec.security))
        aps = _get_unique_aps(aps, self._get_aps_by_visibility(spec.visible))
        matching_aps = list(aps)
        # If APs hostnames are provided, assume the tester knows the location
        # of the AP and skip AFE calls.
        if spec.hostnames is None:
            matching_aps = self._get_aps_by_lab_location(spec.lab_ap,
                                                         matching_aps)

        if spec.configurator_type != ap_spec.CONFIGURATOR_ANY:
            matching_aps = self._get_aps_by_configurator_type(
                           spec.configurator_type, matching_aps)
        if spec.hostnames is not None:
            matching_aps = self.get_aps_by_hostnames(spec.hostnames,
                                                     ap_list=matching_aps)
        if pre_configure:
            for ap in matching_aps:
                ap.set_using_ap_spec(spec)
        return matching_aps


    def turn_off_all_routers(self):
        """Powers down all of the routers."""
        ap_power_cartridge = ap_cartridge.APCartridge()
        for ap in self.ap_list:
            ap.power_down_router()
            ap_power_cartridge.push_configurator(ap)
        ap_power_cartridge.run_configurators()
