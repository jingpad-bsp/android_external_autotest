#!/usr/bin/env python

# Copyright (c) 2013 The Chromium OS Authors. All rights reserved.
# Use of this source code is governed by a BSD-style license that can be
# found in the LICENSE file.

import dbus
import logging
import logging.handlers
import os
import shutil

import common
from autotest_lib.client.bin import utils
from autotest_lib.client.common_lib.cros import xmlrpc_server
from autotest_lib.client.cros import constants


class BluetoothClientXmlRpcDelegate(xmlrpc_server.XmlRpcDelegate):
    """Exposes DUT methods called remotely during Bluetooth autotests.

    All instance methods of this object without a preceding '_' are exposed via
    an XML-RPC server. This is not a stateless handler object, which means that
    if you store state inside the delegate, that state will remain around for
    future calls.
    """

    UPSTART_PATH = 'unix:abstract=/com/ubuntu/upstart'
    UPSTART_MANAGER_PATH = '/com/ubuntu/Upstart'
    UPSTART_MANAGER_IFACE = 'com.ubuntu.Upstart0_6'
    UPSTART_JOB_IFACE = 'com.ubuntu.Upstart0_6.Job'

    UPSTART_ERROR_UNKNOWNINSTANCE = \
            'com.ubuntu.Upstart0_6.Error.UnknownInstance'

    BLUETOOTHD_JOB = 'bluetoothd'

    DBUS_ERROR_SERVICEUNKNOWN = 'org.freedesktop.DBus.Error.ServiceUnknown'

    BLUEZ_SERVICE_NAME = 'org.bluez'
    BLUEZ_MANAGER_PATH = '/'
    BLUEZ_MANAGER_IFACE = 'org.freedesktop.DBus.ObjectManager'
    BLUEZ_ADAPTER_IFACE = 'org.bluez.Adapter1'

    BLUETOOTH_LIBDIR = '/var/lib/bluetooth'

    # Timeout for how long we'll wait for BlueZ and the Adapter to show up
    # after reset.
    ADAPTER_TIMEOUT = 30

    def __init__(self):
        super(BluetoothClientXmlRpcDelegate, self).__init__()

        # Set up the connection to Upstart so we can start and stop services
        # and fetch the bluetoothd job.
        self._upstart_conn = dbus.connection.Connection(self.UPSTART_PATH)
        self._upstart = self._upstart_conn.get_object(
                None,
                self.UPSTART_MANAGER_PATH)

        bluetoothd_path = self._upstart.GetJobByName(
                self.BLUETOOTHD_JOB,
                dbus_interface=self.UPSTART_MANAGER_IFACE)
        self._bluetoothd = self._upstart_conn.get_object(
                None,
                bluetoothd_path)

        # Set up the connection to the D-Bus System Bus and get the object for
        # BlueZ.
        self._system_bus = dbus.SystemBus()
        self._update_bluez()
        self._update_adapter()


    def _update_bluez(self):
        """Store a D-Bus proxy for the Bluetooth daemon in self._bluez.

        @return True on success, False otherwise.

        """
        self._bluez = None
        try:
            self._bluez = self._system_bus.get_object(
                    self.BLUEZ_SERVICE_NAME,
                    self.BLUEZ_MANAGER_PATH)
            logging.debug('bluetoothd is running')
            return True
        except dbus.exceptions.DBusException, e:
            if e.get_dbus_name() == self.DBUS_ERROR_SERVICEUNKNOWN:
                logging.debug('bluetoothd is not running')
                self._bluez = None
                return False
            else:
                raise


    def _update_adapter(self):
        """Store a D-Bus proxy for the local adapter in self._adapter.

        @return True on success, including if there is no local adapter,
            False otherwise.

        """
        self._adapter = None
        if self._bluez is None:
            return False

        objects = self._bluez.GetManagedObjects(
                dbus_interface=self.BLUEZ_MANAGER_IFACE)
        for path, ifaces in objects.iteritems():
            logging.debug('%s -> %r', path, ifaces.keys())
            if self.BLUEZ_ADAPTER_IFACE in ifaces:
                logging.debug('using adapter %s', path)
                self._adapter = self._system_bus.get_object(
                        self.BLUEZ_SERVICE_NAME,
                        path)
                return True
        else:
            return False


    @xmlrpc_server.dbus_safe(False)
    def reset_on(self):
        """Reset the adapter and settings and power up the adapter.

        @return True on success, False otherwise.

        """
        self._reset()
        self._set_powered(True)
        return True


    @xmlrpc_server.dbus_safe(False)
    def reset_off(self):
        """Reset the adapter and settings, leave the adapter powered off.

        @return True on success, False otherwise.

        """
        self._reset()
        return True


    def _reset(self):
        """Reset the Bluetooth adapter and settings."""
        logging.debug('_reset')
        if self._adapter:
            self._set_powered(False)

        try:
            self._bluetoothd.Stop(dbus.Array(signature='s'), True,
                                  dbus_interface=self.UPSTART_JOB_IFACE)
        except dbus.exceptions.DBusException, e:
            if e.get_dbus_name() != self.UPSTART_ERROR_UNKNOWNINSTANCE:
                raise

        for subdir in os.listdir(self.BLUETOOTH_LIBDIR):
            shutil.rmtree(os.path.join(self.BLUETOOTH_LIBDIR, subdir))

        self._bluetoothd.Start(dbus.Array(signature='s'), True,
                               dbus_interface=self.UPSTART_JOB_IFACE)

        # We can't just pass self._update_bluez/adapter to poll_for_condition
        # because we need to check the local state.
        logging.debug('waiting for bluez start')
        utils.poll_for_condition(
                condition=self._update_bluez,
                desc='Bluetooth Daemon has started.',
                timeout=self.ADAPTER_TIMEOUT)

        logging.debug('waiting for bluez to obtain adapter information')
        utils.poll_for_condition(
                condition=self._update_adapter,
                desc='Bluetooth Daemon has adapter information.',
                timeout=self.ADAPTER_TIMEOUT)


    @xmlrpc_server.dbus_safe(False)
    def set_powered(self, powered):
        """Set the adapter power state.

        @param powered: adapter power state to set (True or False).

        @return True on success, False otherwise.

        """
        self._set_powered(powered)
        return True


    def _set_powered(self, powered):
        """Set the adapter power state.

        @param powered: adapter power state to set (True or False).

        """
        logging.debug('_set_powered %r', powered)
        self._adapter.Set(self.BLUEZ_ADAPTER_IFACE, 'Powered', powered,
                          dbus_interface=dbus.PROPERTIES_IFACE)


    @xmlrpc_server.dbus_safe(False)
    def set_discoverable(self, discoverable):
        """Set the adapter discoverable state.

        @param discoverable: adapter discoverable state to set (True or False).

        @return True on success, False otherwise.

        """
        self._adapter.Set(self.BLUEZ_ADAPTER_IFACE,
                          'Discoverable', discoverable,
                          dbus_interface=dbus.PROPERTIES_IFACE)
        return True


    @xmlrpc_server.dbus_safe(False)
    def set_pairable(self, pairable):
        """Set the adapter pairable state.

        @param pairable: adapter pairable state to set (True or False).

        @return True on success, False otherwise.

        """
        self._adapter.Set(self.BLUEZ_ADAPTER_IFACE, 'Pairable', pairable,
                          dbus_interface=dbus.PROPERTIES_IFACE)
        return True


if __name__ == '__main__':
    logging.basicConfig(level=logging.DEBUG)
    handler = logging.handlers.SysLogHandler(address='/dev/log')
    logging.getLogger().addHandler(handler)
    logging.debug('bluetooth_client_xmlrpc_server main...')
    server = xmlrpc_server.XmlRpcServer(
            'localhost',
            constants.BLUETOOTH_CLIENT_XMLRPC_SERVER_PORT)
    server.register_delegate(BluetoothClientXmlRpcDelegate())
    server.run()
