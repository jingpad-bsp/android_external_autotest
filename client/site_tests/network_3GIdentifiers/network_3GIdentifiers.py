# Copyright (c) 2013 The Chromium OS Authors. All rights reserved.
# Use of this source code is governed by a BSD-style license that can be
# found in the LICENSE file.

import logging

from autotest_lib.client.bin import test
from autotest_lib.client.common_lib import error
from autotest_lib.client.cros import network
from autotest_lib.client.cros.cellular import mm

# TODO(armansito): We should really move cros/cellular/pseudomodem/mm1.py to
# cros/cellular/, as it deprecates the old mm1.py. See crosbug.com/37005
from autotest_lib.client.cros.cellular.pseudomodem import mm1, pseudomodem, sim

import flimflam

# Disable pylint warning W1201 because we pass the string to the log as well
# as use it to raise an error, see _ValidateIdentifier().
#     W1201: Specify string format arguments as logging function parameters
# pylint: disable=W1201

SERVICE_REGISTRATION_TIMEOUT = 60

class network_3GIdentifiers(test.test):
    """This test verifies that a modem returns valid identifiers."""
    version = 1

    def _ValidateIdentifier(self, label, device_value, modem_value,
                            min_length, max_length):
        """Validates a specific identifier by matching the values reported by
           Shill and ModemManager as well as verifying its length."""
        if device_value != modem_value:
            message = 'Shill value "%s" does not match MM value "%s"' % \
                      (device_value, modem_value)
            logging.error(message)
            raise error.TestFail(message)
        if (len(device_value) < min_length or len(device_value) > max_length):
            message = 'Invalid %s value "%s"' % (label, device_value)
            logging.error(message)
            raise error.TestFail(message)
        logging.info('    %s = %s' % (label, device_value))

    def _ValidateGsmIdentifiers(self, device_props, service_props, modem_props):
        """Validates GSM identifiers."""
        self._ValidateIdentifier('IMEI',
                                 device_props['Cellular.IMEI'],
                                 modem_props['Imei'],
                                 14, 16)
        self._ValidateIdentifier('IMSI',
                                 device_props['Cellular.IMSI'],
                                 modem_props['Imsi'],
                                 0, 15)
        if self.is_modemmanager:
            operator_identifier = modem_props.get('OperatorIdentifier', '')
            if operator_identifier != '':
                # If modemmanager fails to expose this property, the
                # HomeProvider information is obtained offline from
                # mobile_provider_database. We don't check that case here.
                self._ValidateIdentifier(
                        'HomeProvider.code',
                        device_props['Cellular.HomeProvider']['code'],
                        operator_identifier,
                        5, 6)
            self._ValidateIdentifier('Operator ID',
                                     device_props['Cellular.SIMOperatorID'],
                                     modem_props['OperatorIdentifier'],
                                     5, 6)
            self._ValidateIdentifier('ICCID',
                                     device_props['Cellular.ICCID'],
                                     modem_props['SimIdentifier'],
                                     0, 20)

        self._ValidateIdentifier(
                'ServingOperator.code',
                service_props['Cellular.ServingOperator']['code'],
                modem_props['OperatorCode'],
                5, 6)


    def _ValidateCdmaIdentifiers(self, device_props, modem_props):
        """Validates CDMA identifiers."""
        self._ValidateIdentifier('ESN',
                                 device_props['Cellular.ESN'],
                                 modem_props['Esn'],
                                 8, 8)
        self._ValidateIdentifier('MEID',
                                 device_props['Cellular.MEID'],
                                 modem_props['Meid'],
                                 14, 14)

    def run_once(self, use_pseudomodem=False):
        """Calls by autotest to run this test."""
        self.use_pseudomodem = use_pseudomodem
        fake_sim = sim.SIM(sim.SIM.Carrier('att'),
            mm1.MM_MODEM_ACCESS_TECHNOLOGY_GSM)
        with pseudomodem.TestModemManagerContext(use_pseudomodem, sim=fake_sim):
            flim = flimflam.FlimFlam()
            flim.SetDebugTags(
                'dbus+service+device+modem+cellular+portal+network+'
                'manager+dhcp')
            network.ResetAllModems(flim)

            device = flim.FindCellularDevice()
            if not device:
                raise error.TestFail('Failed to find cellular device')
            service = flim.FindCellularService(SERVICE_REGISTRATION_TIMEOUT)
            if not service:
                raise error.TestFail('Cellular device failed to register with '
                                     'network.')
            device_props = device.GetProperties(utf8_strings=True)
            service_props = service.GetProperties(utf8_strings=True)
            self.is_modemmanager = 'freedesktop' in device_props['DBus.Service']
            if self.is_modemmanager and not device_props['Cellular.SIMPresent']:
                raise error.TestFail('Test requires a valid SIM')

            manager, modem_path = mm.PickOneModem('')
            modem = manager.GetModem(modem_path)
            modem_props = modem.GetModemProperties()

            logging.debug('shill service properties: %s', service_props)
            logging.debug('shill device_properties: %s', device_props)
            logging.debug('mm properties: %s', modem_props)

            technology_family = device_props['Cellular.Family']
            if technology_family == 'GSM':
                logging.info('Validating GSM identifiers')
                self._ValidateGsmIdentifiers(device_props, service_props,
                                             modem_props)
            elif technology_family == 'CDMA':
                logging.info('Validating CDMA identifiers')
                self._ValidateCdmaIdentifiers(device_props, modem_props)
            else:
                raise error.TestFail('Invalid technology family %s' %
                                     technology_family)
