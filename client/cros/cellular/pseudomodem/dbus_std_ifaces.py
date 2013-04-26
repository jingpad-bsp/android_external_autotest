# Copyright (c) 2012 The Chromium OS Authors. All rights reserved.
# Use of this source code is governed by a BSD-style license that can be
# found in the LICENSE file.

"""
Python implementation of the standard interfaces:
  - org.freedesktop.DBus.Properties
  - org.freedesktop.DBus.Introspectable (TODO(armansito): May not be necessary)
  - org.freedesktop.DBus.ObjectManager

"""

import dbus
import dbus.service
import dbus.types
import logging
import mm1

class MMPropertyError(mm1.MMError):
    """
    MMPropertyError is raised by DBusProperties methods
    to indicate that a value for the given interface or
    property could not be found.

    """

    UNKNOWN_PROPERTY = 0
    UNKNOWN_INTERFACE = 1

    def __init__(self, errno, *args, **kwargs):
        super(MMPropertyError, self).__init__(errno, args, kwargs)

    def _Setup(self):
        self._error_name_base = mm1.I_MODEM_MANAGER
        self._error_name_map = {
            self.UNKNOWN_PROPERTY : '.UnknownProperty',
            self.UNKNOWN_INTERFACE : '.UnknownInterface'
        }

class DBusProperties(dbus.service.Object):
    """
    == org.freedesktop.DBus.Properties ==

    This serves as the abstract base class for all objects that expose
    properties. Each instance holds a mapping from DBus interface names to
    property-value mappings, which are provided by the subclasses.

    """

    def __init__(self, path, bus=None, config=None):
        """
        Args:
            bus -- The pydbus bus object.
            path -- The DBus object path of this object.
            config -- This is an optional dictionary that can be used to
                      initialize the property dictionary with values other
                      than the ones provided by |_InitializeProperties|. The
                      dictionary has to contain a mapping from DBus interfaces
                      to property-value pairs, and all contained keys must
                      have been initialized during |_InitializeProperties|,
                      i.e. if config contains any keys that have not been
                      already set in the internal property dictionary, an
                      error will be raised. (See DBusProperties.Set)

        """
        if not path:
            raise TypeError(('A value for "path" has to be provided that is '
                'not "None".'))
        if bus:
          dbus.service.Object.__init__(self, bus, path)
        else:
          dbus.service.Object.__init__(self, None, None)
        self.path = path
        self.bus = bus
        self._properties = self._InitializeProperties()

        if config:
            for key, props in config:
                for prop, val in props:
                    self.Set(key, prop, val)

    def SetBus(self, bus):
        self.bus = bus
        self.add_to_connection(bus, self.path)

    def SetUInt32(self, interface_name, property_name, value):
        self.Set(interface_name, property_name, dbus.types.UInt32(value))

    def SetInt32(self, interface_name, property_name, value):
        self.Set(interface_name, property_name, dbus.types.Int32(value))

    @dbus.service.method(mm1.I_PROPERTIES,
                         in_signature='ss', out_signature='v')
    def Get(self, interface_name, property_name):
        """
        Returns the value matching the given property and interface.

        Args:
            interface_name -- The DBus interface name.
            property_name -- The property name.

        Returns:
            The value matching the given property and interface.

        Raises:
            MMPropertyError, if the given interface_name or property_name
            is not exposed by this object.

        """
        logging.info(
            '%s: Get(%s, %s)',
            self.path,
            interface_name,
            property_name)
        val = self.GetAll(interface_name).get(property_name, None)
        if val is None:
            message = ("Property '%s' not implemented for interface '%s'." %
                (property_name, interface_name))
            logging.info(message)
            raise MMPropertyError(
                MMPropertyError.UNKNOWN_PROPERTY, message)
        return val

    @dbus.service.method(mm1.I_PROPERTIES, in_signature='ssv')
    def Set(self, interface_name, property_name, value):
        """
        Sets the value matching the given property and interface.

        Args:
            interface_name -- The DBus interface name.
            property_name -- The property name.

        Emits:
            PropertiesChanged

        Raises:
            MMPropertyError, if the given |interface_name| or |property_name|
            is not exposed by this object.

        """
        logging.info(
            '%s: Set(%s, %s)',
            self.path,
            interface_name,
            property_name)
        props = self.GetAll(interface_name)
        if property_name not in props:
            raise MMPropertyError(
                MMPropertyError.UNKNOWN_PROPERTY,
                ("Property '%s' not implemented for "
                "interface '%s'.") %
                (property_name, interface_name))
        props[property_name] = value
        changed = { property_name : value }
        inv = self._InvalidatedPropertiesForChangedValues(changed)
        self.PropertiesChanged(interface_name, changed, inv)

    @dbus.service.method(mm1.I_PROPERTIES,
                         in_signature='s', out_signature='a{sv}')
    def GetAll(self, interface_name):
        """
        Returns all property-value pairs that match the given interface.

        Args:
            interface_name -- The DBus interface name.

        Raises:
            MMPropertyError, if the given interface_name is not exposed
            by this object.

        """
        logging.info(
            '%s: GetAll(%s)',
            self.path,
            interface_name)
        props = self._properties.get(interface_name, None)
        if props is None:
            raise MMPropertyError(
                MMPropertyError.UNKNOWN_INTERFACE,
                "Object does not implement interface '%s'." %
                interface_name)
        return props

    @dbus.service.signal(mm1.I_PROPERTIES, signature='sa{sv}as')
    def PropertiesChanged(
            self,
            interface_name,
            changed_properties,
            invalidated_properties):
        """
        This signal is emitted by Set, when the value of a property is changed.

        Args:
            interface_name -- The interface the changed properties belong to.
            changed_properties -- Dictionary containing the changed properties
                    and their new values.
            invalidated_properties -- List of properties that were invalidated
                    when properties changed.

        """
        logging.info(('Properties Changed on interface: %s Changed Properties:'
            ' %s InvalidatedProperties: %s.', interface_name,
            str(changed_properties), str(invalidated_properties)))

    def GetInterfacesAndProperties(self):
        return self._properties

    def _InvalidatedPropertiesForChangedValues(self, changed):
        """
        Called by Set, returns the list of property names that should become
        invalidated given the properties and their new values contained in
        changed. Subclasses can override this method; the default implementation
        returns an empty list.

        """
        return []

    def _InitializeProperties(self):
        """
        Called at instantiation. Subclasses have to override this method and
        return a dictionary containing mappings from implemented interfaces to
        dictionaries of property-value mappings.

        """
        raise NotImplementedError()


class DBusObjectManager(dbus.service.Object):
    """
    == org.freedesktop.DBus.ObjectManager ==

    This interface, included in rev. 0.17 of the DBus specification, allows a
    generic way to control the addition and removal of Modem objects, as well
    as the addition and removal of interfaces in the given objects.

    """

    def __init__(self, bus, path):
        dbus.service.Object.__init__(self, bus, path)
        self.devices = []
        self.bus = bus
        self.path = path

    def Add(self, device):
        """
        Adds a device to the list of devices that are managed by this modem
        manager.

        Args:
            device -- Device to add.

        Emits:
            InterfacesAdded

        """
        self.devices.append(device)
        self.InterfacesAdded(device.path, device.GetInterfacesAndProperties())

    def Remove(self, device):
        """
        Removes a device from the list of devices that are managed by this
        modem manager.

        Args:
            device -- Device to remove.

        Emits:
            InterfacesRemoved

        """
        if device in self.devices:
            self.devices.remove(device)
        interfaces = device.GetInterfacesAndProperties().keys()
        device.remove_from_connection()
        self.InterfacesRemoved(device.path, interfaces)

    @dbus.service.method(mm1.I_OBJECT_MANAGER, out_signature='a{oa{sa{sv}}}')
    def GetManagedObjects(self):
        """
        Returns:
            A dictionary containing all objects and their properties. The
            keys to the dictionary are object paths which are mapped to
            dictionaries containing mappings from DBus interface names to
            property-value pairs.

        """
        results = {}
        for device in self.devices:
            results[dbus.types.ObjectPath(device.path)] = (
                    device.GetInterfacesAndProperties())
        logging.info('%s: GetManagedObjects: %s', self.path,
                     ', '.join(results.keys()))
        return results

    @dbus.service.signal(mm1.I_OBJECT_MANAGER, signature='oa{sa{sv}}')
    def InterfacesAdded(self, object_path, interfaces_and_properties):
        logging.info((self.path + ': InterfacesAdded(' + object_path +
                     ', ' + str(interfaces_and_properties)) + ')')

    @dbus.service.signal(mm1.I_OBJECT_MANAGER, signature='oas')
    def InterfacesRemoved(self, object_path, interfaces):
        logging.info((self.path + ': InterfacesRemoved(' + object_path +
                     ', ' + str(interfaces) + ')'))
