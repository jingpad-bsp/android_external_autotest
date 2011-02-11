# Copyright (c) 2011 The Chromium OS Authors. All rights reserved.
# Use of this source code is governed by a BSD-style license that can be
# found in the LICENSE file.

import dbus
import json
import logging
import os.path
from xml.dom.minidom import parse, parseString

from autotest_lib.client.bin import test, utils
from autotest_lib.client.common_lib import error
from autotest_lib.client.cros import constants, login

class security_DbusMap(test.test):
    version = 1

    def load_baseline(self):
        """
        Return a list of interface names we expect to be owned
        by chronos.
        """
        # Figure out path to baseline file, by looking up our own path.
        bpath = os.path.abspath(__file__)
        bpath = os.path.join(os.path.dirname(bpath), 'baseline')
        return self.load_dbus_data_from_disk(bpath)


    def write_dbus_data_to_disk(self, dbus_list, file_path):
        """Writes the given dbus data to a given path to a json file.
        Args:
            dbus_list: list of dbus dictionaries to write to disk.
            file_path: the path to the file to write the data to.
        """
        file_handle = open(file_path, 'w')
        my_json = json.dumps(dbus_list, sort_keys=True, indent=2)
        file_handle.write(my_json)
        file_handle.close()


    def load_dbus_data_from_disk(self, file_path):
        """Loads dbus data from a given path to a json file.
        Args:
            file_path: path to the file as a string.
        Returns:
            A list of the dictionary representation of the dbus data loaded.
            The dictionary format is the same as returned by walk_object().
        """
        file_handle = open(file_path, 'r')
        dbus_data = json.loads(file_handle.read())
        file_handle.close()
        return dbus_data


    def sort_dbus_tree(self, tree):
        """Sorts a an aray of dbus dictionaries in alphabetical order.
             All levels of the tree are sorted.
        Args:
            tree: the array to sort. Modified in-place.
        """
        tree.sort(key=lambda x: x['Object_name'])
        for dbus_object in tree:
            dbus_object['interfaces'].sort(key=lambda x: x['interface'])
            for interface in dbus_object['interfaces']:
                interface['methods'].sort()


    def compare_dbus_trees(self, current, baseline):
        """Compares two dbus dictionaries and return the delta.
           The comparison only returns what is in the current (LHS) and not
           in the baseline (RHS). If you want the reverse, call again
           with the arguments reversed.
        Args:
            current: dbus tree you want to compare against the baseline.
            baseline: dbus tree baseline.
        Returns:
            A list of dictionary representations of the additional dbus
            objects, if there is a difference. Otherwise it returns an
            empty list. The format of the dictionaries is the same as the
            one returned in walk_object().
        """

        # Build the key map of what is in the baseline.
        bl_object_names = [bl_object['Object_name'] for bl_object in baseline]

        new_items = []
        for dbus_object in current:
            if dbus_object['Object_name'] in bl_object_names:
                index = bl_object_names.index(dbus_object['Object_name'])
                bl_object_interfaces = baseline[index]['interfaces']
                bl_interface_names = [name['interface'] for name in
                                      bl_object_interfaces]

                # If we have a new interface/method we need to build the shell.
                new_object = {'Object_name':dbus_object['Object_name'],
                              'interfaces':[]}

                for interface in dbus_object['interfaces']:
                    if interface['interface'] in bl_interface_names:
                        # This interface is in the baseline, check the methods.
                        index = bl_interface_names.index(interface['interface'])
                        bl_methods = set(bl_object_interfaces[index]['methods'])
                        methods = set(interface['methods'])
                        difference = methods.difference(bl_methods)
                        if (len(difference) > 0):
                            # This is a new method we need to track.
                            new_methods = {'interface':interface['interface'],
                                           'methods':list(difference)}
                            new_object['interfaces'].append(new_methods)
                            new_items.append(new_object)
                    else:
                        # This is a new interface we need to track.
                        new_object['interfaces'].append(interface)
                        new_items.append(new_object)
            else:
                # This is a new object we need to track.
                new_items.append(dbus_object)
        return new_items


    def walk_object(self, bus, object_name, start_path, dbus_objects):
        """Walks the given bus and object returns a dictionary representation.
           The formate of the dictionary is as follows:
           {
               Object_name: "string"
               interfaces:
               [
                   interface: "string"
                   methods:
                   [
                       "string1",
                       "string2"
                   ]
               ]
           }
           Note that the decision to capitalize Object_name is just
           a way to force it to appear above the interface-list it
           corresponds to, when pretty-printed by the json dumper.
           This makes it more logical for humans to read/edit.
        Args:
            bus: the bus to query, usually system.
            object_name: the name of the dbus object to walk.
            start_path: the path inside of the object in which to start walking
            dbus_objects: current list of dbus objects in the given object
        Returns:
            A dictionary representation of a dbus object
        """
        remote_object = bus.get_object(object_name,start_path)
        unknown_iface = dbus.Interface(remote_object,
                                       'org.freedesktop.DBus.Introspectable')
        # Convert the string to an xml DOM object we can walk.
        xml = parseString(unknown_iface.Introspect())
        for child in xml.childNodes:
            if ((child.nodeType == 1) and (child.localName == u'node')):
                interfaces = child.getElementsByTagName('interface')
                for interface in interfaces:
                    # For storage we will have a dictionary with two keys.
                    # TODO(jimhebert): Also get the signals out of here,
                    # in addition to the methods.
                    methods = interface.getElementsByTagName('method')
                    method_list = []
                    for method in methods:
                        method_list.append(method.getAttribute('name'))
                    # Create the dictionary.
                    dictionary = {'interface':interface.getAttribute('name'),
                                  'methods':method_list}
                    if dictionary not in dbus_objects:
                        dbus_objects.append(dictionary)
                nodes = child.getElementsByTagName('node')
                for node in nodes:
                    name = node.getAttribute('name')
                    if start_path[-1] != '/':
                            start_path = start_path + '/'
                    new_name = start_path + name
                    self.walk_object(bus, object_name, new_name, dbus_objects)
        return {'Object_name':('%s' % object_name), 'interfaces':dbus_objects}


    def mapper_main(self):
        # Currently we only dump the SystemBus. Accessing the SessionBus says:
        # "ExecFailed: /usr/bin/dbus-launch terminated abnormally with the
        # following error: Autolaunch requested, but X11 support not compiled
        # in."
        # If this changes at a later date, add dbus.SessionBus() to the dict.
        # We've left the code structured to support walking more than one bus
        # for such an eventuality.

        buses = {'System Bus': dbus.SystemBus()}

        for busname in buses.keys():
            bus = buses[busname]
            remote_dbus_object = bus.get_object('org.freedesktop.DBus',
                                                '/org/freedesktop/DBus')
            iface = dbus.Interface(remote_dbus_object, 'org.freedesktop.DBus')
            dbus_list = []
            for i in iface.ListNames():
                # There are some strange listings like ":1" which appear after
                # certain names. Ignore these since we just need the names.
                if i.startswith(':'):
                    continue
                dbus_list.append(self.walk_object(bus, i, '/', []))
        self.sort_dbus_tree(dbus_list)

        baseline = self.load_baseline()
        self.sort_dbus_tree(baseline)

        # Compare trees to find added API's.
        newapis = self.compare_dbus_trees(dbus_list, baseline)
        if (len(newapis) > 0):
            logging.error("New API's to review:")
            logging.error(json.dumps(newapis, sort_keys=True, indent=2))
        # Swap arguments to find missing API's.
        missing_apis = self.compare_dbus_trees(baseline, dbus_list)
        if (len(missing_apis) > 0):
            logging.error("Missing API's to consider removing from baseline:")
            logging.error(json.dumps(missing_apis, sort_keys=True, indent=2))

        if (len(newapis) + len(missingapis)) > 0:
            raise error.TestFail('Baseline mismatch')


    def run_once(self):
        """
        Enumerates all discoverable interfaces, methods, and signals
        in dbus-land. Verifies that it matches an expected set.
        """
        login.wait_for_browser()
        self.mapper_main()
