# Copyright 2015 The Chromium OS Authors. All rights reserved.
# Use of this source code is governed by a BSD-style license that can be
# found in the LICENSE file.

import dbus
import logging
import syslog
import time

from autotest_lib.client.common_lib import error
from autotest_lib.client.common_lib.cros import process_watcher
from autotest_lib.client.cros import dbus_util

SERVICE_NAME = 'org.chromium.leaderd'
# In test images, we add a supplementary set of rules that expand the DBus
# access policy to tolerate us claiming this name and sending messages to
# these services.
TEST_SERVICE_NAME_PREFIX = 'org.chromium.leaderd.test'

DBUS_INTERFACE_MANAGER = 'org.chromium.leaderd.Manager'
DBUS_INTERFACE_GROUP = 'org.chromium.leaderd.Group'
DBUS_PATH_MANAGER = '/org/chromium/leaderd/Manager'

GROUP_PROPERTY_MEMBERS = 'MemberUUIDs'


def get_nth_service_name(n):
    """Get the DBus service name for the Nth instance of leaderd.

    @param n: int starting from 0 inclusive.
    @return string: DBus service name for Nth instance.

    """
    return '%s.TestInstance%d' % (TEST_SERVICE_NAME_PREFIX, n)


def confirm_leaderd_started(service_name=SERVICE_NAME,
                            bus=None,
                            timeout_seconds=10):
    """Confirm that an instance of leaderd is responding to queries over DBus.

    @param service_name: string well known DBus connection name of instance.
    @param bus: dbus.Bus instance.
    @param timeout_seconds: number of seconds to wait for leaderd to respond.

    """
    if bus is None:
        bus = dbus.SystemBus()
    start_time = time.time()
    while time.time() - start_time < timeout_seconds:
        try:
            manager = dbus.Interface(
                    bus.get_object(service_name, DBUS_PATH_MANAGER),
                    DBUS_INTERFACE_MANAGER)
            if manager.Ping() == 'Hello world!':
                return
        except:
            pass
        time.sleep(0.5)

    raise error.TestFail('Timed out before leaderd at %s started.' %
                         service_name)


class LeaderdHelper(object):
    """Helper object for manipulating leaderd."""

    def start_instance(self,
                       leaderd_service_name,
                       peerd_service_name,
                       handler_name,
                       verbosity_level=3):
        """Start an instance of leaderd.

        @param leaderd_service_name: string well known DBus service name to
                claim for this instance of leaderd.
        @param peerd_service_name: string well known DBus service name of
                peerd service for this leaderd instance to depend on.
        @param handler_name: string protocol handler name to use from the
                webserver.
        @param verbosity_level: integer leaderd logging verbosity level.
        @return ProcessWatcher object that should be closed to clean up the
                started process.

        """
        # Here, we're forced to launch leaderd without upstart, because
        # upstart is configured to launch a single instance of leaderd,
        # rather than many instances in parallel.
        syslog.syslog('Starting leaderd service=%s' % leaderd_service_name)
        watcher = process_watcher.ProcessWatcher(
                '/usr/bin/leaderd',
                args=['--v=%d' % verbosity_level,
                      '--service_name=%s' % leaderd_service_name, '--peerd_service_name=%s' % peerd_service_name,
                      '--protocol_handler_name=%s' % handler_name,
                     ],
                minijail_config=process_watcher.MinijailConfig(user='leaderd',
                                                               group='leaderd'))
        watcher.start()
        confirm_leaderd_started(service_name=leaderd_service_name)
        return watcher


    def join_group(self, group_id, instance_number=None, bus=None):
        """Join a group on a given instance of leaderd.

        @param group_id: string UUID of group to join.
        @param instance_number: instance number of leaderd to join to the group.
                If not provided, joins the global leaderd instance to the group.
        @param bus: dbus.Bus instance if something other than the system bus
                should be used to communicate with this instance.
        @return string DBus path of group.

        """
        logging.info('Joining leaderd group %s.', group_id)
        service_name = SERVICE_NAME
        if instance_number is not None:
            service_name = get_nth_service_name(instance_number)
        if bus is None:
            # This is a global singleton DBus connection that stays
            # open until explicitly closed or the process exits.
            bus = dbus.SystemBus()
        manager = dbus.Interface(
                bus.get_object(service_name, DBUS_PATH_MANAGER),
                DBUS_INTERFACE_MANAGER)
        # Note that this instance of leaderd will leave this group
        # when the DBus connection held by |bus| dies.
        group_path = manager.JoinGroup(dbus.String(str(group_id)),
                                       dbus.Dictionary(dict(), 'sv'))
        return dbus_util.dbus2primitive(group_path)


    def get_members(self, group_path, instance_number=None, bus=None):
        """Get the members of a group.

        @param group_path: string path of group on DBus.
        @param instance_number: integer instance of leaderd to contact.
                Defaults to the normal system service instance.
        @param bus: instance of dbus.Bus if something other than the system bus
                should be used.
        @return list of string UUIDs representing peers in the group as
                seen by this instance of leaderd.

        """
        service_name = SERVICE_NAME
        if instance_number is not None:
            service_name = get_nth_service_name(instance_number)
        if bus is None:
            # This is a global singleton DBus connection that stays
            # open until explicitly closed or the process exits.
            bus = dbus.SystemBus()
        group = dbus.Interface(
                bus.get_object(service_name, group_path),
                dbus.PROPERTIES_IFACE)
        members = group.Get(DBUS_INTERFACE_GROUP, GROUP_PROPERTY_MEMBERS)
        return dbus_util.dbus2primitive(members)
