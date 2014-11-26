# Copyright 2014 The Chromium OS Authors. All rights reserved.
# Use of this source code is governed by a BSD-style license that can be
# found in the LICENSE file.

"""This module provides functions to manage servers in server database
(defined in global config section AUTOTEST_SERVER_database).

create(hostname, role=None, note=None)
    Create a server with given role, with status backup.

delete(hostname)
    Delete a server from the database. If the server is in primary status, its
    roles will be replaced by a backup server first.

modify(hostname, role=None, status=None, note=None, delete=False,
       attribute=None, value=None)
    Modify a server's role, status, note, or attribute:
    1. Add role to a server. If the server is in primary status, proper actions
       like service restart will be executed to enable the role.
    2. Delete a role from a server. If the server is in primary status, proper
       actions like service restart will be executed to disable the role.
    3. Change status of a server. If the server is changed from or to primary
       status, proper actions like service restart will be executed to enable
       or disable each role of the server.
    4. Change note of a server. Note is a field you can add description about
       the server.
    5. Change/delete attribute of a server. Attribute can be used to store
       information about a server. For example, the max_processes count for a
       drone.

"""

# TODO(dshi): crbug.com/424778 This module currently doesn't have any logic to
# do action server operations, e.g., restart scheduler to enable a drone. All it
# does is to update database. This helps the CL to be smaller for review. Next
# CL will include actual server action logic.

import datetime

import common

import django.core.exceptions
from autotest_lib.client.common_lib.global_config import global_config
from autotest_lib.frontend import setup_django_environment
from autotest_lib.frontend.server import models as server_models


class ServerActionError(Exception):
    """Exception raised when action on server failed.
    """


def _add_role(server, role):
    """Add a role to the server.

    @param server: An object of server_models.Server.
    @param role: Role to be added to the server.

    @raise ServerActionError: If role is failed to be added.
    """
    server_models.validate(role=role)
    if server_models.ServerRole.objects.filter(server=server, role=role):
        raise ServerActionError('Server %s already has role %s.' %
                                (server.hostname, role))

    if (role in server_models.ServerRole.ROLES_REQUIRE_UNIQUE_INSTANCE and
        server.status == server_models.Server.STATUS.PRIMARY):
        servers = server_models.Server.objects.filter(
                roles__role=role, status=server_models.Server.STATUS.PRIMARY)
        if len(servers) >= 1:
            raise ServerActionError('Role %s must be unique. Server %s '
                                    'already has role %s.' %
                                    (role, servers[0].hostname, role))
    server_models.ServerRole.objects.create(server=server, role=role)

    print 'Role %s is added to server %s.' % (role, server.hostname)


def _delete_role(server, role):
    """Delete a role from the server.

    @param server: An object of server_models.Server.
    @param role: Role to be deleted from the server.

    @raise ServerActionError: If role is failed to be deleted.
    """
    server_models.validate(role=role)
    server_roles = server_models.ServerRole.objects.filter(server=server,
                                                           role=role)
    if not server_roles:
        raise ServerActionError('Server %s does not have role %s.' %
                                (server.hostname, role))

    if server.status == server_models.Server.STATUS.PRIMARY:
        servers = server_models.Server.objects.filter(
                roles__role=role, status=server_models.Server.STATUS.PRIMARY)
        if len(servers) == 1:
            print ('Role %s is required in an Autotest instance. Please '
                   'add the role to another server.' % role)
    # Role should be deleted after all action is completed.
    server_roles[0].delete()

    print 'Role %s is deleted from server %s.' % (role, server.hostname)


def _change_status(server, status):
    """Change the status of the server.

    @param server: An object of server_models.Server.
    @param status: New status of the server.

    @raise ServerActionError: If status is failed to be changed.
    """
    server_models.validate(status=status)
    if server.status == status:
        raise ServerActionError('Server %s already has status of %s.' %
                                (server.hostname, status))
    if (not server.roles.all() and
            status == server_models.Server.STATUS.PRIMARY):
        raise ServerActionError('Server %s has no role associated. Server '
                                'must have a role to be in status primary.'
                                % server.hostname)

    unique_roles = server.roles.filter(
            role__in=server_models.ServerRole.ROLES_REQUIRE_UNIQUE_INSTANCE)
    if unique_roles and status == server_models.Server.STATUS.PRIMARY:
        for role in unique_roles:
            servers = server_models.Server.objects.filter(
                    roles__role=role.role,
                    status=server_models.Server.STATUS.PRIMARY)
            if len(servers) == 1:
                raise ServerActionError('Role %s must be unique. Server %s '
                                        'already has the role.' %
                                        (role.role, servers[0].hostname))
    old_status = server.status
    server.status = status
    server.save()

    print ('Status of server %s is changed from %s to %s. Affected roles: %s' %
           (server.hostname, old_status, status,
            ', '.join([r.role for r in server.roles.all()])))


def _delete_attribute(server, attribute):
    """Delete the attribute from the host.

    @param server: An object of server_models.Server.
    @param attribute: Name of an attribute of the server.
    """
    attributes = server.attributes.filter(attribute=attribute)
    if not attributes:
        raise ServerActionError('Server %s does not have attribute %s' %
                                (server.hostname, attribute))
    attributes[0].delete()
    print 'Attribute %s is deleted from server %s.' % (attribute,
                                                       server.hostname)


def _change_attribute(server, attribute, value):
    """Change the value of an attribute of the server.

    @param server: An object of server_models.Server.
    @param attribute: Name of an attribute of the server.
    @param value: Value of the attribute of the server.

    @raise ServerActionError: If the attribute already exists and has the
                              given value.
    """
    attributes = server_models.ServerAttribute.objects.filter(
            server=server, attribute=attribute)
    if attributes and attributes[0].value == value:
        raise ServerActionError('Attribute %s for Server %s already has '
                                'value of %s.' %
                                (attribute, server.hostname, value))
    if attributes:
        old_value = attributes[0].value
        attributes[0].value = value
        attributes[0].save()
        print ('Attribute `%s` of server %s is changed from %s to %s.' %
                     (attribute, server.hostname, old_value, value))
    else:
        server_models.ServerAttribute.objects.create(
                server=server, attribute=attribute, value=value)
        print ('Attribute `%s` of server %s is set to %s.' %
               (attribute, server.hostname, value))


def use_server_db():
    """Check if use_server_db is enabled in configuration.

    @return: True if use_server_db is set to True in global config.
    """
    return global_config.get_config_value(
            'SERVER', 'use_server_db', default=False, type=bool)


def get_servers(hostname=None, role=None, status=None):
    """Find servers with given role and status.

    @param hostname: hostname of the server.
    @param role: Role of server, default to None.
    @param status: Status of server, default to None.

    @return: A list of server objects with given role and status.
    """
    filters = {}
    if hostname:
        filters['hostname'] = hostname
    if role:
        filters['roles__role'] = role
    if status:
        filters['status'] = status
    return server_models.Server.objects.filter(**filters)


def get_server_details(servers, table=False, summary=False):
    """Get a string of given servers' details.

    The method can return a string of server information in 3 different formats:
    A detail view:
        Hostname     : server2
        Status       : primary
        Roles        : drone
        Attributes   : {'max_processes':300}
        Date Created : 2014-11-25 12:00:00
        Date Modified: None
        Note         : Drone in lab1
    A table view:
        Hostname | Status  | Roles     | Date Created    | Date Modified | Note
        server1  | backup  | scheduler | 2014-11-25 23:45:19 |           |
        server2  | primary | drone     | 2014-11-25 12:00:00 |           | Drone
    A summary view:
        scheduler      : server1(backup), server3(primary),
        host_scheduler :
        drone          : server2(primary),
        devserver      :
        database       :
        suite_scheduler:
        crash_server   :
        No Role        :

    The method returns detail view of each server and a summary view by default.
    If `table` is set to True, only table view will be returned.
    If `summary` is set to True, only summary view will be returned.

    @param servers: A list of servers to get details.
    @param table: True to return a table view instead of a detail view,
                  default is set to False.
    @param summary: True to only show the summary of roles and status of
                    given servers.

    @return: A string of the information of given servers.
    """
    # Format string to display a table view.
    # Hostname, Status, Roles, Date Created, Date Modified, Note
    TABLEVIEW_FORMAT = ('%(hostname)-30s | %(status)-7s | %(roles)-20s | '
                        '%(date_created)-19s | %(date_modified)-19s | %(note)s')

    result = ''
    if not table and not summary:
        for server in servers:
            result += '\n' + str(server)
    elif table:
        result += (TABLEVIEW_FORMAT %
                   {'hostname':'Hostname', 'status':'Status',
                    'roles':'Roles', 'date_created':'Date Created',
                    'date_modified':'Date Modified', 'note':'Note'})
        for server in servers:
            roles = ','.join([r.role for r in server.roles.all()])
            result += '\n' + (TABLEVIEW_FORMAT %
                              {'hostname':server.hostname,
                               'status': server.status or '',
                               'roles': roles,
                               'date_created': server.date_created,
                               'date_modified': server.date_modified or '',
                               'note': server.note or ''})
    elif summary:
        result += 'Roles and status of servers:\n\n'
        for role, _ in server_models.ServerRole.ROLE.choices():
            servers_of_role = [s for s in servers if role in
                               [r.role for r in s.roles.all()]]
            result += '%-15s: ' % role
            for server in servers_of_role:
                result += '%s(%s), ' % (server.hostname, server.status)
            result += '\n'
        servers_without_role = [s.hostname for s in servers
                                if not s.roles.all()]
        result += '%-15s: %s' % ('No Role', ', '.join(servers_without_role))

    return result


def verify_server(exist=True):
    """Decorator to check if server with given hostname exists in the database.

    @param exist: Set to True to confirm server exists in the database, raise
                  exception if not. If it's set to False, raise exception if
                  server exists in database. Default is True.

    @raise ServerActionError: If `exist` is True and server does not exist in
                              the database, or `exist` is False and server exists
                              in the database.
    """
    def deco_verify(func):
        """Wrapper for the decorator.

        @param func: Function to be called.
        """
        def func_verify(*args, **kwargs):
            """Decorator to check if server exists.

            If exist is set to True, raise ServerActionError is server with
            given hostname is not found in server database.
            If exist is set to False, raise ServerActionError is server with
            given hostname is found in server database.

            @param func: function to be called.
            @param args: arguments for function to be called.
            @param kwargs: keyword arguments for function to be called.
            """
            hostname = kwargs['hostname']
            try:
                server = server_models.Server.objects.get(hostname=hostname)
            except django.core.exceptions.ObjectDoesNotExist:
                server = None

            if not exist and server:
                raise ServerActionError('Server %s already exists.' %
                                        hostname)
            if exist and not server:
                raise ServerActionError('Server %s does not exist in the '
                                        'database.' % hostname)
            if server:
                kwargs['server'] = server
            return func(*args, **kwargs)
        return func_verify
    return deco_verify


@verify_server(exist=False)
def create(hostname, role=None, note=None):
    """Create a new server.

    The status of new server will always be backup, user need to call
    atest server modify hostname --status primary
    to set the server's status to primary.

    @param hostname: hostname of the server.
    @param role: role of the new server, default to None.
    @param note: notes about the server, default to None.

    @return: A Server object that contains the server information.
    """
    server_models.validate(hostname=hostname, role=role)
    server = server_models.Server.objects.create(
            hostname=hostname, status=server_models.Server.STATUS.BACKUP,
            note=note, date_created=datetime.datetime.now())
    server_models.ServerRole.objects.create(server=server, role=role)
    return server


@verify_server()
def delete(hostname, server=None):
    """Delete given server from server database.

    @param hostname: hostname of the server to be deleted.
    @param server: Server object from database query, this argument should be
                   injected by the verify_server_exists decorator.

    @raise ServerActionError: If delete server action failed, e.g., server is
            not found in database or server is primary but no backup is found.
    """
    print 'Deleting server %s from server database.' % hostname

    if (use_server_db() and
            server.status == server_models.Server.STATUS.PRIMARY):
        print ('Server %s is in status primary, need to disable its '
               'current roles first.' % hostname)
        for role in server.roles.all():
            _delete_role(server, role.role)

    server.delete()
    print 'Server %s is deleted from server database.' % hostname


@verify_server()
def modify(hostname, role=None, status=None, delete=False, note=None,
           attribute=None, value=None, server=None):
    """Modify given server with specified actions.

    @param hostname: hostname of the server to be modified.
    @param role: Role to be added to the server.
    @param status: Modify server status.
    @param delete: True to delete given role from the server, default to False.
    @param note: Note of the server.
    @param attribute: Name of an attribute of the server.
    @param value: Value of an attribute of the server.
    @param server: Server object from database query, this argument should be
                   injected by the verify_server_exists decorator.

    @raise InvalidDataError: If the operation failed with any wrong value of
                             the arguments.
    @raise ServerActionError: If any operation failed.
    """
    if role:
        if not delete:
            _add_role(server, role)
        else:
            _delete_role(server, role)

    if status:
        _change_status(server, status)

    if note is not None:
        server.note = note
        server.save()

    if attribute and value:
        _change_attribute(server, attribute, value)
    elif attribute and delete:
        _delete_attribute(server, attribute)

    return server


def get_drones():
    """Get a list of drones in status primary.

    @return: A list of drones in status primary.
    """
    servers = get_servers(role=server_models.ServerRole.ROLE.DRONE,
                          status=server_models.Server.STATUS.PRIMARY)
    return [s.hostname for s in servers]
