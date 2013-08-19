# Copyright (c) 2012 The Chromium Authors. All rights reserved.
# Use of this source code is governed by a BSD-style license that can be
# found in the LICENSE file.

"""File containing class to build all available ap_configurators."""

import logging

from autotest_lib.server.cros import chaos_config
from autotest_lib.server.cros.chaos_ap_configurators import ap_cartridge
from autotest_lib.server.cros.chaos_ap_configurators import \
        ap_configurator_config


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
        'BelkinF9KAPConfigurator':
            [PREFIX + 'belkinF9K_ap_configurator',
                'BelkinF9KAPConfigurator'],
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
        chaos_ap_list = chaos_config.ChaosAPList()

        self.ap_list = []
        for ap in chaos_ap_list:
            module_name, configurator_class = \
                    self.CONFIGURATOR_MAP[ap.get_class()]
            module = __import__(module_name, fromlist=configurator_class)
            configurator = module.__dict__[configurator_class]
            if not webdriver_ready and configurator.is_dynamic():
                from autotest_lib.server.cros.chaos_ap_configurators import \
                    download_chromium_prebuilt
                download_chromium_prebuilt.check_webdriver_ready()
                webdriver_ready = True

            self.ap_list.append(configurator(ap_config=ap))


    def _cleanup_ap_spec(self, key, value):
        """Validates AP attribute.

        @param key: a string, one of BANDS, SECURITIES or MODES.
        @param value: a list of strings, values of key.

        @returns a list of strings, valid values for key. Or None.
        """
        # Used to fetch AP attributes such as bands, modes, securities
        config = ap_configurator_config.APConfiguratorConfig()

        attr_dict = {
            self.BANDS: config.VALID_BANDS,
            self.MODES: config.VALID_MODES,
            self.SECURITIES: config.VALID_SECURITIES,
            }

        invalid_value = set(value).difference(attr_dict[key])
        if invalid_value:
            logging.warning('Ignored invalid %s: %r', key, invalid_value)
            value = list(set(value) - invalid_value)
            logging.info('Remaining valid value for %s = %r', key, value)

        return value


    def _get_aps_by_visibility(self, visible=True):
        """Returns all configurators that support setting visibility.

        @param visibility = True if SSID should be visible; False otherwise.

        @returns aps: a set of APConfigurators"""
        if visible:
            return set(self.ap_list)

        return set(filter(lambda ap: ap.is_visibility_supported(),
                          self.ap_list))


    def _get_aps_by_mode(self, mode):
        """Returns all configurators that support a given 802.11 mode.

        @param mode: an 802.11 modes.

        @returns aps: a set of APConfigurators.
        """
        if not mode:
            return set(self.ap_list)

        aps = []
        for ap in self.ap_list:
            modes = ap.get_supported_modes()
            for d in modes:
                if mode in d['modes']:
                    aps.append(ap)
        return set(aps)


    def _get_aps_with_modes(self, modes, ap_list):
        """Returns all configurators that support a given 802.11 mode.

        @param mode: a list of hex numbers, 802.11 modes.
        @param ap_list: a list of APConfigurator objects.

        @returns aps: a list of APConfigurators. Or None.
        """
        modes = self._cleanup_ap_spec(self.MODES, modes)
        if not modes:
            logging.warning('No valid modes found.')
            return None

        aps = []
        for ap in ap_list:
            bands_and_modes = ap.get_supported_modes()
            # FIXME(tgao): would mixing modes across bands cause any issue?
            ap_modes = set()
            for d in bands_and_modes:
                if self.MODES in d:
                    ap_modes = ap_modes.union(set(d[self.MODES]))
            if set(modes).issubset(ap_modes):
                logging.debug('Found ap by mode = %r', ap.host_name)
                aps.append(ap)
        return aps


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


    def _get_aps_with_securities(self, securities, ap_list):
        """Returns all configurators that support a given security mode.

        @param securities: a list of integers, security mode.
        @param ap_list: a list of APConfigurator objects.

        @returns aps: a list of APConfigurators. Or None.
        """
        securities = self._cleanup_ap_spec(self.SECURITIES, securities)
        if not securities:
            logging.warning('No valid security found.')
            return None

        aps = []
        for ap in ap_list:
            for security in securities:
                if not ap.is_security_mode_supported(security):
                    break
            else:  # ap supports all securities
                logging.debug('Found ap by security = %r', ap.host_name)
                aps.append(ap)
        return aps


    def _get_aps_by_band(self, band):
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
                if d['band'] == band:
                    aps.append(ap)
        return set(aps)


    def _get_aps_with_bands(self, bands, ap_list):
        """Returns all APs that support bands.

        @param bands: a list of strings, bands supported.
        @param ap_list: a list of APConfigurator objects.

        @returns aps: a list of APConfigurators. Or None.
        """
        bands = self._cleanup_ap_spec(self.BANDS, bands)
        if not bands:
            logging.warning('No valid bands found.')
            return None

        aps = []
        for ap in ap_list:
            bands_and_channels = ap.get_supported_bands()
            ap_bands = [d['band'] for d in bands_and_channels if 'band' in d]
            if set(bands).issubset(set(ap_bands)):
                logging.debug('Found ap by band = %r', ap.host_name)
                aps.append(ap)
        return aps


    def get_aps_configurators_by_hostnames(self, hostnames):
        """Returns speciic APs by host name.

        @param hostnames: a list of strings, AP's wan_hostname defined in
                          ../chaos_dynamic_ap_list.conf.

        @return a list of APConfigurators.
        """
        aps=[]
        for ap in self.ap_list:
            if ap.host_name in hostnames:
                aps.append(ap)
        return aps


    def _get_aps_with_hostnames(self, hostnames, ap_list):
        """Returns specific APs by host name.

        @param hostnames: a list of strings, AP's wan_hostname defined in
                          ../chaos_dynamic_ap_list.conf.
        @param ap_list: a list of APConfigurator objects.

        @return a list of APConfigurators.
        """
        aps = []
        for ap in ap_list:
            if ap.host_name in hostnames:
                logging.info('Found AP by hostname %s', ap.host_name)
                aps.append(ap)

        return aps


    def get_ap_configurators_by_spec(self, ap_spec=None, pre_configure=False):
        """Returns available configurators meeting spec.

        @param ap_spec: a validated ap_spec object
        @param pre_configure: boolean, True to set all of the configuration
                              options for the APConfigurator object using the
                              given ap_spec; False otherwise.  An ap_spec must
                              be passed for this to have any effect.
        @returns aps: a list of APConfigurator objects
        """
        if not ap_spec:
            return self.ap_list

        band_aps = self._get_aps_by_band(ap_spec.band)
        mode_aps = self._get_aps_by_mode(ap_spec.mode)
        security_aps = self._get_aps_by_security(ap_spec.security)
        visible_aps = self._get_aps_by_visibility(ap_spec.visible)
        matching_aps = list(band_aps & mode_aps & security_aps & visible_aps)
        if pre_configure:
            for ap in matching_aps:
                ap.set_using_ap_spec(ap_spec)
        return matching_aps


    def get_ap_configurators(self, spec=None):
        """Returns available configurators meeting spec.

        Caller may request APs based on the following attributes:
         - BANDS, a list of strings, bands supported.
         - MODES, a list of hex numbers, 802.11 modes supported.
         - SECURITIES, a list of strings, security methods supported.
         - HOSTNAMES, a list of strings, AP wan_hostname.

        Interpretation rules:
         - if an attribute is not present in spec, it's not used to select APs.
         - caller should only specify an attribute s/he cares about testing.
         - if HOSTNAMES is specified, only the APs specified are returned.
           All other attributes are IGNORED.
         - in case of a list of (>1) strings, logical AND is applied, e.g.
           dual-band (2.4GHz AND 5GHz).
         - if multiple attributes are specified, logical AND is applied.
           Evaluation order is securities, then bands, then modes (which could
           depend on bands as input).

        Sample spec values and expected returns:
        1. spec = None or empty dict
           Return all APs
        2. spec = dict(bands=['2.4GHz', '5GHz'])
           Return all dual-band APs
        3. spec = dict(modes=[0x00010, 0x00100], securities=[2])
           Return all APs which support both 802.11b AND 802.11g modes AND
           PSK security
        4. spec = dict(hostnames=['chromeos3-row1-rack1-host6',
                                  'chromeos3-row1-rack1-host7'])
           Return only the two APs specified.

        @param spec: a dict of AP attributes, see explanation above.
        @returns aps: a list of APConfigurator objects. Or None.
        """
        aps = self.ap_list
        if not spec:
            logging.info('No spec included, return all APs')
            return aps

        hostnames = spec.get(self.HOSTNAMES, None)
        if hostnames:  # Fast path to return specified APs
            logging.info('Select APs by hostname: %r', hostnames)
            aps = self._get_aps_with_hostnames(hostnames, aps)
            return aps

        securities = spec.get(self.SECURITIES, None)
        bands = spec.get(self.BANDS, None)
        modes = spec.get(self.MODES, None)

        if securities:
            logging.info('Select APs by securities: %r', securities)
            aps = self._get_aps_with_securities(securities, aps)
        if aps and bands:
            logging.info('Select APs by bands: %r', bands)
            aps = self._get_aps_with_bands(bands, aps)
        if aps and modes:
            logging.info('Select APs by modes: %r', modes)
            aps = self._get_aps_with_modes(modes, aps)

        return aps


    def turn_off_all_routers(self):
        """Powers down all of the routers."""
        ap_power_cartridge = ap_cartridge.APCartridge()
        for ap in self.ap_list:
            ap.power_down_router()
            ap_power_cartridge.push_configurator(ap)
        ap_power_cartridge.run_configurators()
