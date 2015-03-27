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
GROUP_PROPERTY_LEADER_UUID = 'LeaderUUID'

def _get_bus(bus):
    """Get a dbus.Bus object to use.

    @param bus: dbus.Bus object to use or None.

    """
    if bus is None:
        # This is a global singleton DBus connection that stays
        # open until explicitly closed or the process exits.
        bus = dbus.SystemBus()
    return bus


def get_nth_service_name(n):
    """Get the DBus service name for the Nth instance of leaderd.

    @param n: int starting from 0 inclusive.
    @return string: DBus service name for Nth instance.

    """
    if n is None:
        return SERVICE_NAME
    return '%s.TestInstance%d' % (TEST_SERVICE_NAME_PREFIX, n)


def confirm_leaderd_started(service_name=SERVICE_NAME,
                            bus=None,
                            timeout_seconds=10):
    """Confirm that an instance of leaderd is responding to queries over DBus.

    @param service_name: string well known DBus connection name of instance.
    @param bus: dbus.Bus instance.
    @param timeout_seconds: number of seconds to wait for leaderd to respond.

    """
    bus = _get_bus(bus)
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
        service_name = get_nth_service_name(instance_number)
        bus = _get_bus(bus)
        manager = dbus.Interface(
                bus.get_object(service_name, DBUS_PATH_MANAGER),
                DBUS_INTERFACE_MANAGER)
        # Note that this instance of leaderd will leave this group
        # when the DBus connection held by |bus| dies.
        group_path = manager.JoinGroup(dbus.String(str(group_id)),
                                       dbus.Dictionary(dict(), 'sv'))
        return dbus_util.dbus2primitive(group_path)


    def set_score(self, group_path, score, instance_number=None, bus=None):
        """Set the score of a particular group.

        @param group_path: string DBus path of group to set score on.
        @param score: integer score.
        @param instance_number: instance number of leaderd to join to the group.
                If not provided, joins the global leaderd instance to the group.
        @param bus: dbus.Bus instance if something other than the system bus
                should be used to communicate with this instance.

        """
        bus = _get_bus(bus)
        service_name = get_nth_service_name(instance_number)
        group = dbus.Interface(
                bus.get_object(service_name, group_path),
                DBUS_INTERFACE_GROUP)
        group.SetScore(dbus.Int32(score))


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
        service_name = get_nth_service_name(instance_number)
        bus = _get_bus(bus)
        group = dbus.Interface(
                bus.get_object(service_name, group_path),
                dbus.PROPERTIES_IFACE)
        members = group.Get(DBUS_INTERFACE_GROUP, GROUP_PROPERTY_MEMBERS)
        return dbus_util.dbus2primitive(members)


    def get_leader(self, group_path, instance_number=None, bus=None):
        """Get the leader according to a particular group.

        @param group_path: string DBus path of group to set score on.
        @param instance_number: instance number of leaderd to join to the group.
                If not provided, joins the global leaderd instance to the group.
        @param bus: dbus.Bus instance if something other than the system bus
                should be used to communicate with this instance.
        @return string leader id found on group.

        """
        service_name = get_nth_service_name(instance_number)
        bus = _get_bus(bus)
        group = dbus.Interface(
                bus.get_object(service_name, group_path),
                dbus.PROPERTIES_IFACE)
        leader = group.Get(DBUS_INTERFACE_GROUP, GROUP_PROPERTY_LEADER_UUID)
        return dbus_util.dbus2primitive(leader)


    def confirm_instances_see_each_other(self, group_paths, expected_peer_ids,
                                         timeout_seconds=5, bus=None):
        """Confirm that some previously created instances agree they're all
        members of a group.

        @param group_paths: dictionary mapping from instance numbers to string
                DBus group paths of the group on those instances.
        @param expected_peer_ids: list of string peer ids that should be listed
                in each group's membership list.
        @param timeout_seconds: number of seconds to wait for convergence.
        @param bus: dbus.Bus instance if something other than the system bus
                should be used to communicate with this instance.
        @return True iff all groups list |expected_peer_ids| as group members.

        """
        start_time = time.time()
        while time.time() - start_time < timeout_seconds:
            for instance_number, group_path in group_paths.iteritems():
                actual_peer_ids = sorted(self.get_members(
                        group_path, instance_number=instance_number, bus=bus))
                if actual_peer_ids != expected_peer_ids:
                    logging.debug('Expected to find group members %r, but got '
                                  '%r on instance %d.',
                                  expected_peer_ids,
                                  actual_peer_ids,
                                  instance_number)
                    time.sleep(1)
                    continue  # Found an instance with a bad membership list.
            return True  # All instances agree on the correct membership.
        return False  # Timed out.


    def confirm_instances_follow_leader(self, group_paths, expected_leader_id,
                                        timeout_seconds=30, bus=None):
        """Confirm that some previously created instances agree on a leader.

        @param group_paths: dictionary mapping from instance numbers to string
                DBus group paths of the group on those instances.
        @param expected_leader_id: string identifier of leader (a UUID).
        @param timeout_seconds: number of seconds to wait for convergence.
        @param bus: dbus.Bus instance if something other than the system bus
                should be used to communicate with this instance.
        @return True iff all groups give |expected_leader_id| as their leader.

        """
        start_time = time.time()
        while time.time() - start_time < timeout_seconds:
            for instance_number, group_path in group_paths.iteritems():
                actual_leader_id = self.get_leader(
                        group_path, instance_number=instance_number, bus=bus)
                if actual_leader_id != expected_leader_id:
                    logging.debug('Expected to find leader id %s, but got %s '
                                  'on instance %d.',
                                  expected_leader_id,
                                  actual_leader_id,
                                  instance_number)
                    time.sleep(1)
                    continue  # Found a peer that disagrees about the leader.
            return True  # Everyone agrees on the expected leader.
        return False  # Timed out.
