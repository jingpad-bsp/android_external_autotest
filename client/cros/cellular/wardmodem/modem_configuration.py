# Copyright (c) 2013 The Chromium OS Authors. All rights reserved.
# Use of this source code is governed by a BSD-style license that can be
# found in the LICENSE file.

import logging
import os
import pprint
import sys

import wardmodem_exceptions as wme

CONF_DIR_NAME = 'configurations'
DEFAULT_CONF_FILE = 'base.conf'
MODEM_CONF_FILE = {
}

class ModemConfiguration(object):
    """
    All modem specific configuration needed by WardModem.

    This class serves the dual purpose of loading the configuration data needed
    by different parts of wardmodem in a single place, and providing
    documentation regarding the configuration parameters available in the file.

    """

    def __init__(self, modem=None):
        """
        @param modem The modem for which the configuration needs to be loaded.
                |modem| can be None. In that case, only the configuration for
                the base modem is loaded.
                Otherwise, |modem| must be a key in |MODEM_CONF_FILE|.
        """
        self._logger = logging.getLogger(__name__)

        if modem and modem not in MODEM_CONF_FILE:
            raise wme.WardModemSetupException('Unknown modem: |%s|' % modem)

        # TODO(pprabhu) Figure out if it makes sense to use Configurable to
        # (de)serialize configuration. See crbug.com/252475
        # First load the default configuration
        self._logger.info('Loading basic configuration.')
        self.base_conf = self._load_conf(DEFAULT_CONF_FILE)
        self._logger.debug('Basic configuration:\n%s',
                           pprint.pformat(self.base_conf))

        # Now load the plugin conf data.
        self.plugin_conf = {}
        if modem:
            self._logger.info('Loading modem specific configuration for modem '
                              '|%s|', modem)
            self.plugin_conf = self._load_conf(MODEM_CONF_FILE[modem])
        self._logger.debug('Plugin configuration:\n%s',
                           pprint.pformat(self.plugin_conf))

        self._populate_config()


    def _populate_config(self):
        """
        Assign configuration data loaded into self variable for easy access.

        """
        # The basic map from AT commands to wardmodem actions common to all
        # modems.
        self.base_at_to_wm_action_map = self.base_conf['at_to_wm_action_map']

        # The map from AT commands to wardmodem actions specific to the current
        # modem.
        self.plugin_at_to_wm_action_map = (
                self.plugin_conf.get('at_to_wm_action_map', {}))

        # The basic map from wardmodem responses to AT commands common to all
        # modems.
        self.base_wm_response_to_at_map = (
                self.base_conf['wm_response_to_at_map'])

        # The map from wardmodem responses to AT commands specific to the
        # current modem.
        self.plugin_wm_response_to_at_map = (
                self.plugin_conf.get('wm_response_to_at_map', {}))

        # The state machines loaded by all modems.
        self.base_state_machines = self.base_conf['state_machines']

        # The state machines specific to the current modem.
        self.plugin_state_machines =  self.plugin_conf.get('state_machines', [])


        # The modemmanager plugin to be used for the modem.
        self.mm_plugin = (
                self.plugin_conf.get('mm_plugin', self.base_conf['mm_plugin']))


        # The string to be prepended to all AT commands from modemmanager to
        # modem.
        self.mm_to_modem_at_prefix = (
                self.plugin_conf.get('mm_to_modem_at_prefix',
                                     self.base_conf['mm_to_modem_at_prefix']))

        # The string to be appended to all AT commands from modemmanager to
        # modem.
        self.mm_to_modem_at_suffix = (
                self.plugin_conf.get('mm_to_modem_at_suffix',
                                     self.base_conf['mm_to_modem_at_suffix']))

        # The string to be prepended to all AT commands from modem to
        # modemmanager.
        self.modem_to_mm_at_prefix = (
                self.plugin_conf.get('modem_to_mm_at_prefix',
                                     self.base_conf['modem_to_mm_at_prefix']))

        # The string to be appended to all AT commands from modem to
        # modemmanager.
        self.modem_to_mm_at_suffix = (
                self.plugin_conf.get('modem_to_mm_at_suffix',
                                     self.base_conf['modem_to_mm_at_suffix']))


    def _load_conf(self, conf_file):
        """
        Load the configuration data from file.

        @param conf_file Name of the file to load from.

        @return The conf data loaded from file.

        """
        # The configuration file is an executable python file. Since the file
        # name is known only at run-time, we must find the module directory and
        # manually point execfile to the directory for loading the configuration
        # file.
        current_module = sys.modules[__name__]
        dir_name = os.path.dirname(current_module.__file__)
        full_path = os.path.join(dir_name, CONF_DIR_NAME, conf_file)
        conf = {}
        execfile(full_path, conf)
        # These entries added by execfile are a nuisance in pprint'ing
        del conf['__builtins__']
        return conf
