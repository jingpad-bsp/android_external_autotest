#!/usr/bin/env python

# Copyright (c) 2013 The Chromium OS Authors. All rights reserved.
# Use of this source code is governed by a BSD-style license that can be
# found in the LICENSE file.

import dbus
import json
import logging
import logging.handlers
import os
import shutil

import common
from autotest_lib.client.bin import utils
from autotest_lib.client.common_lib.cros import xmlrpc_server
from autotest_lib.client.common_lib.cros.bluetooth import bluetooth_socket
from autotest_lib.client.cros import constants


class BluetoothDeviceXmlRpcDelegate(xmlrpc_server.XmlRpcDelegate):
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
    BLUEZ_DEVICE_IFACE = 'org.bluez.Device1'
    BLUEZ_PROFILE_MANAGER_PATH = '/org/bluez'
    BLUEZ_PROFILE_MANAGER_IFACE = 'org.bluez.ProfileManager1'

    BLUETOOTH_LIBDIR = '/var/lib/bluetooth'

    # Timeout for how long we'll wait for BlueZ and the Adapter to show up
    # after reset.
    ADAPTER_TIMEOUT = 30

    def __init__(self):
        super(BluetoothDeviceXmlRpcDelegate, self).__init__()

        # Open the Bluetooth Control socket to the kernel which provides us
        # raw management access to the Bluetooth Host Subsystem. Read the list
        # of adapter indexes to determine whether or not this device has a
        # Bluetooth Adapter or not.
        self._control = bluetooth_socket.BluetoothControlSocket()
        self._has_adapter = len(self._control.read_index_list()) > 0

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

        # Set up the connection to the D-Bus System Bus, get the object for
        # the Bluetooth Userspace Daemon (BlueZ) and that daemon's object for
        # the Bluetooth Adapter.
        self._system_bus = dbus.SystemBus()
        self._update_bluez()
        self._update_adapter()


    def _update_bluez(self):
        """Store a D-Bus proxy for the Bluetooth daemon in self._bluez.

        This may be called in a loop until it returns True to wait for the
        daemon to be ready after it has been started.

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

        This may be called in a loop until it returns True to wait for the
        daemon to be ready, and have obtained the adapter information itself,
        after it has been started.

        Since not all devices will have adapters, this will also return True
        in the case where we have obtained an empty adapter index list from the
        kernel.

        @return True on success, including if there is no local adapter,
            False otherwise.

        """
        self._adapter = None
        if self._bluez is None:
            return False
        if not self._has_adapter:
            return True

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


    def has_adapter(self):
        """Return if an adapter is present.

        This will only return True if we have determined both that there is
        a Bluetooth adapter on this device (kernel adapter index list is not
        empty) and that the Bluetooth daemon has exported an object for it.

        @return True if an adapter is present, False if not.

        """
        return self._has_adapter and self._adapter is not None


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
        if not powered and not self._adapter:
            # Return success if we are trying to power off an adapter that's
            # missing or gone away, since the expected result has happened.
            return True
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
        if not discoverable and not self._adapter:
            # Return success if we are trying to make an adapter that's
            # missing or gone away, undiscoverable, since the expected result
            # has happened.
            return True
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


    @xmlrpc_server.dbus_safe(False)
    def get_adapter_properties(self):
        """Read the adapter properties from the Bluetooth Daemon.

        @return the properties as a JSON-encoded dictionary on success,
            the value False otherwise.

        """
        objects = self._bluez.GetManagedObjects(
                dbus_interface=self.BLUEZ_MANAGER_IFACE)
        adapter = objects[self._adapter.object_path][self.BLUEZ_ADAPTER_IFACE]
        return json.dumps(adapter)


    def read_info(self):
        """Read the adapter information from the Kernel.

        @return the information as a JSON-encoded tuple of:
          ( address, bluetooth_version, manufacturer_id,
            supported_settings, current_settings, class_of_device,
            name, short_name )

        """
        return json.dumps(self._control.read_info(0))


    @xmlrpc_server.dbus_safe(False)
    def get_devices(self):
        """Read information about remote devices known to the adapter.

        @return the properties of each device as a JSON-encoded array of
            dictionaries on success, the value False otherwise.

        """
        objects = self._bluez.GetManagedObjects(
                dbus_interface=self.BLUEZ_MANAGER_IFACE)
        devices = []
        for path, ifaces in objects.iteritems():
            if self.BLUEZ_DEVICE_IFACE in ifaces:
                devices.append(objects[path][self.BLUEZ_DEVICE_IFACE])
        return json.dumps(devices)


    @xmlrpc_server.dbus_safe(False)
    def start_discovery(self):
        """Start discovery of remote devices.

        Obtain the discovered device information using get_devices(), called
        stop_discovery() when done.

        @return True on success, False otherwise.

        """
        self._adapter.StartDiscovery(dbus_interface=self.BLUEZ_ADAPTER_IFACE)
        return True


    @xmlrpc_server.dbus_safe(False)
    def stop_discovery(self):
        """Stop discovery of remote devices.

        @return True on success, False otherwise.

        """
        self._adapter.StopDiscovery(dbus_interface=self.BLUEZ_ADAPTER_IFACE)
        return True


    @xmlrpc_server.dbus_safe(False)
    def register_profile(self, path, uuid, options):
        """Register new profile (service).

        @param path: Path to the profile object.
        @param uuid: Service Class ID of the service as string.
        @param options: Dictionary of options for the new service, compliant
                        with BlueZ D-Bus Profile API standard.

        @return True on success, False otherwise.

        """
        profile_manager = dbus.Interface(
                              self._system_bus.get_object(
                                  self.BLUEZ_SERVICE_NAME,
                                  self.BLUEZ_PROFILE_MANAGER_PATH),
                              self.BLUEZ_PROFILE_MANAGER_IFACE)
        profile_manager.RegisterProfile(path, uuid, options)
        return True


if __name__ == '__main__':
    logging.basicConfig(level=logging.DEBUG)
    handler = logging.handlers.SysLogHandler(address='/dev/log')
    formatter = logging.Formatter(
            'bluetooth_device_xmlrpc_server: [%(levelname)s] %(message)s')
    handler.setFormatter(formatter)
    logging.getLogger().addHandler(handler)
    logging.debug('bluetooth_device_xmlrpc_server main...')
    server = xmlrpc_server.XmlRpcServer(
            'localhost',
            constants.BLUETOOTH_DEVICE_XMLRPC_SERVER_PORT)
    server.register_delegate(BluetoothDeviceXmlRpcDelegate())
    server.run()
