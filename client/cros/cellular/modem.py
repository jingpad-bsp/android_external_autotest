#!/usr/bin/python
# Copyright (c) 2012 The Chromium OS Authors. All rights reserved.
# Use of this source code is governed by a BSD-style license that can be
# found in the LICENSE file.

import dbus
import os

from autotest_lib.client.cros.cellular import cellular

MMPROVIDERS = [ 'org.chromium', 'org.freedesktop' ]


class Modem(object):

    MODEM_INTERFACE = 'org.freedesktop.ModemManager.Modem'
    SIMPLE_MODEM_INTERFACE = 'org.freedesktop.ModemManager.Modem.Simple'
    CDMA_MODEM_INTERFACE = 'org.freedesktop.ModemManager.Modem.Cdma'
    GSM_MODEM_INTERFACE = 'org.freedesktop.ModemManager.Modem.Gsm'
    GOBI_MODEM_INTERFACE = 'org.chromium.ModemManager.Modem.Gobi'
    GSM_CARD_INTERFACE = 'org.freedesktop.ModemManager.Modem.Gsm.Card'
    GSM_SMS_INTERFACE = 'org.freedesktop.ModemManager.Modem.Gsm.SMS'
    GSM_NETWORK_INTERFACE = 'org.freedesktop.ModemManager.Modem.Gsm.Network'
    PROPERTIES_INTERFACE = 'org.freedesktop.DBus.Properties'

    GSM_MODEM = 1
    CDMA_MODEM = 2

    # MM_MODEM_GSM_ACCESS_TECH (not exported)
    # From /usr/include/mm/mm-modem.h
    _MM_MODEM_GSM_ACCESS_TECH_UNKNOWN = 0
    _MM_MODEM_GSM_ACCESS_TECH_GSM = 1
    _MM_MODEM_GSM_ACCESS_TECH_GSM_COMPACT = 2
    _MM_MODEM_GSM_ACCESS_TECH_GPRS = 3
    _MM_MODEM_GSM_ACCESS_TECH_EDGE = 4
    _MM_MODEM_GSM_ACCESS_TECH_UMTS = 5
    _MM_MODEM_GSM_ACCESS_TECH_HSDPA = 6
    _MM_MODEM_GSM_ACCESS_TECH_HSUPA = 7
    _MM_MODEM_GSM_ACCESS_TECH_HSPA = 8

    # Mapping of modem technologies to cellular technologies
    _ACCESS_TECH_TO_TECHNOLOGY = {
        _MM_MODEM_GSM_ACCESS_TECH_GSM: cellular.Technology.WCDMA,
        _MM_MODEM_GSM_ACCESS_TECH_GSM_COMPACT: cellular.Technology.WCDMA,
        _MM_MODEM_GSM_ACCESS_TECH_GPRS: cellular.Technology.GPRS,
        _MM_MODEM_GSM_ACCESS_TECH_EDGE: cellular.Technology.EGPRS,
        _MM_MODEM_GSM_ACCESS_TECH_UMTS: cellular.Technology.WCDMA,
        _MM_MODEM_GSM_ACCESS_TECH_HSDPA: cellular.Technology.HSDPA,
        _MM_MODEM_GSM_ACCESS_TECH_HSUPA: cellular.Technology.HSUPA,
        _MM_MODEM_GSM_ACCESS_TECH_HSPA: cellular.Technology.HSDUPA,
    }

    def __init__(self, manager, path):
        self.bus = manager.bus
        self.service = manager.service
        self.path = path

    def Modem(self):
       obj = self.bus.get_object(self.service, self.path)
       return dbus.Interface(obj, Modem.MODEM_INTERFACE)

    def SimpleModem(self):
        obj = self.bus.get_object(self.service, self.path)
        return dbus.Interface(obj, Modem.SIMPLE_MODEM_INTERFACE)

    def CdmaModem(self):
        obj = self.bus.get_object(self.service, self.path)
        return dbus.Interface(obj, Modem.CDMA_MODEM_INTERFACE)

    def GobiModem(self):
        obj = self.bus.get_object(self.service, self.path)
        return dbus.Interface(obj, Modem.GOBI_MODEM_INTERFACE)

    def GsmModem(self):
        obj = self.bus.get_object(self.service, self.path)
        return dbus.Interface(obj, Modem.GSM_MODEM_INTERFACE)

    def GsmCard(self):
        obj = self.bus.get_object(self.service, self.path)
        return dbus.Interface(obj, Modem.GSM_CARD_INTERFACE)

    def GsmSms(self):
        obj = self.bus.get_object(self.service, self.path)
        return dbus.Interface(obj, Modem.GSM_SMS_INTERFACE)

    def GsmNetwork(self):
        obj = self.bus.get_object(self.service, self.path)
        return dbus.Interface(obj, Modem.GSM_NETWORK_INTERFACE)

    def GetAll(self, iface):
        obj = self.bus.get_object(self.service, self.path)
        obj_iface = dbus.Interface(obj, Modem.PROPERTIES_INTERFACE)
        return obj_iface.GetAll(iface)

    def _GetModemInterfaces(self):
        return [
            Modem.MODEM_INTERFACE,
            Modem.SIMPLE_MODEM_INTERFACE,
            Modem.CDMA_MODEM_INTERFACE,
            Modem.GSM_MODEM_INTERFACE,
            Modem.GSM_NETWORK_INTERFACE,
            Modem.GOBI_MODEM_INTERFACE]

    def GetModemProperties(self):
        props = dict()
        for iface in self._GetModemInterfaces():
            try:
                d = self.GetAll(iface)
            except dbus.exceptions.DBusException, e:
                continue
            if d:
                for k, v in d.iteritems():
                    props[k] = v

        return props

    def GetAccessTechnology(self):
        props = self.GetModemProperties()
        tech = props.get('AccessTechnology')
        return Modem._ACCESS_TECH_TO_TECHNOLOGY[tech]

    def _GetRegistrationState(self):
        try:
            network = self.GsmNetwork()
            (status, code, name) = network.GetRegistrationInfo()
            # TODO(jglasgow): HOME - 1, ROAMING - 5
            return status == 1 or status == 5
        except dbus.exceptions.DBusException, e:
            pass

        cdma_modem = manager.CdmaModem()
        try:
            cdma, evdo = cdma_modem.GetRegistrationState()
            return cdma > 0 or evdo > 0
        except dbus.exceptions.DBusException, e:
            pass

        return False

    def ModemIsRegistered(self):
        """Ensure that modem is registered on the network."""
        return self._GetRegistrationState()

    def ModemIsRegisteredUsing(self, technology):
        """Ensure that modem is registered on the network with a technology."""

        if not self.ModemIsRegistered():
            return False

        reported_tech = self.GetAccessTechnology()

        # TODO(jglasgow): Remove this mapping.  Basestation and
        # reported technology should be identical.
        BASESTATION_TO_REPORTED_TECHNOLOGY = {
            cellular.Technology.GPRS:      cellular.Technology.GPRS,
            cellular.Technology.EGPRS:     cellular.Technology.GPRS,
            cellular.Technology.WCDMA:     cellular.Technology.HSDUPA,
            cellular.Technology.HSDPA:     cellular.Technology.HSDUPA,
            cellular.Technology.HSUPA:     cellular.Technology.HSDUPA,
            cellular.Technology.HSDUPA:    cellular.Technology.HSDUPA,
            cellular.Technology.HSPA_PLUS: cellular.Technology.HSPA_PLUS
        }

        return BASESTATION_TO_REPORTED_TECHNOLOGY[technology] == reported_tech


class ModemManager(object):
    INTERFACE = 'org.freedesktop.ModemManager'

    def __init__(self, provider=None):
        self.bus = dbus.SystemBus()
        self.provider = provider or os.getenv('MMPROVIDER') or 'org.chromium'
        self.service = '%s.ModemManager' % self.provider
        self.path = '/%s/ModemManager' % (self.provider.replace('.', '/'))
        self.manager = dbus.Interface(
            self.bus.get_object(self.service, self.path),
            ModemManager.INTERFACE)


def EnumerateDevices(manager=None):
    """ Enumerate all modems in the system

    Args:
        manager - the specific manager to use, if None check all known managers

    Returns:
        a list of (ModemManager object, modem dbus path)
    """
    SERVICE_UNKNOWN = 'org.freedesktop.DBus.Error.ServiceUnknown'
    if manager:
        managers = [manager]
    else:
        managers = []
    for provider in MMPROVIDERS:
        try:
            managers.append(ModemManager(provider))
        except dbus.exceptions.DBusException, e:
            if e._dbus_error_name != SERVICE_UNKNOWN:
                raise

    result = []
    for m in managers:
        for path in m.manager.EnumerateDevices():
            result.append((m, path))

    return result


def PickOneModem(modem_pattern, manager=None):
    """ Pick a modem

    If a machine has a single modem, managed by one one of the
    MMPROVIDERS, return the dbus path and a ModemManager object for
    that modem.

    Args:
        modem_pattern - pattern that should match the modem path
        manager - the specific manager to use, if None check all known managers

    Returns:
        Modem object

    Raises:
        ValueError - if there are no matching modems, or there are more
                     than one
    """
    devices = EnumerateDevices(manager)

    matches = [Modem(m, path) for m, path in devices if modem_pattern in path]
    if not matches:
        raise ValueError("No modems had substring: " + modem_pattern)
    if len(matches) > 1:
        raise ValueError("Expected only one modem, got: " +
                         ", ".join([modem.path for modem in matches]))
    return matches[0]
