# Copyright 2014 The Chromium OS Authors. All rights reserved.
# Use of this source code is governed by a BSD-style license that can be
# found in the LICENSE file.

import mox
import unittest

import common

import django.core.exceptions
from autotest_lib.client.common_lib import base_utils as utils
from autotest_lib.frontend import setup_django_environment
from autotest_lib.frontend.server import models as server_models
from autotest_lib.site_utils import server_manager


class QueriableList(list):
    """A mock list object supports queries including filter and all.
    """

    def filter(self, **kwargs):
        """Mock the filter call in django model.
        """
        raise NotImplementedError()


    def all(self):
        """Return all items in the list.

        @return: All items in the list.
        """
        return [item for item in self]


class ServerManagerUnittests(mox.MoxTestBase):
    """Unittest for testing server_manager module.
    """

    def setUp(self):
        """Initialize the unittest."""
        super(ServerManagerUnittests, self).setUp()

        # Initialize test objects.
        self.DRONE_ROLE = mox.MockObject(
                server_models.ServerRole,
                attrs={'role': server_models.ServerRole.ROLE.DRONE})
        self.SCHEDULER_ROLE = mox.MockObject(
                server_models.ServerRole,
                attrs={'role': server_models.ServerRole.ROLE.SCHEDULER})
        self.DRONE_ATTRIBUTE = mox.MockObject(
                server_models.ServerAttribute,
                attrs={'attribute': 'max_processes', 'value':1})
        self.PRIMARY_DRONE = mox.MockObject(
                server_models.Server,
                attrs={'hostname': 'primary_drone_hostname',
                       'status': server_models.Server.STATUS.PRIMARY,
                       'roles': QueriableList([self.DRONE_ROLE]),
                       'attributes': QueriableList([self.DRONE_ATTRIBUTE])})
        self.BACKUP_DRONE = mox.MockObject(
                server_models.Server,
                attrs={'hostname': 'backup_drone_hostname',
                       'status': server_models.Server.STATUS.BACKUP,
                       'roles': QueriableList([self.DRONE_ROLE]),
                       'attributes': QueriableList([self.DRONE_ATTRIBUTE])})
        self.PRIMARY_SCHEDULER = mox.MockObject(
                server_models.Server,
                attrs={'hostname': 'primary_scheduler_hostname',
                       'status': server_models.Server.STATUS.PRIMARY,
                       'roles': QueriableList([self.SCHEDULER_ROLE]),
                       'attributes': QueriableList([])})
        self.BACKUP_SCHEDULER = mox.MockObject(
                server_models.Server,
                attrs={'hostname': 'backup_scheduler_hostname',
                       'status': server_models.Server.STATUS.BACKUP,
                       'roles': QueriableList([self.SCHEDULER_ROLE]),
                       'attributes': QueriableList([])})

        self.mox.StubOutWithMock(server_manager, 'use_server_db')
        self.mox.StubOutWithMock(server_models.Server.objects, 'create')
        self.mox.StubOutWithMock(server_models.Server.objects, 'filter')
        self.mox.StubOutWithMock(server_models.Server.objects, 'get')
        self.mox.StubOutWithMock(server_models.ServerRole.objects, 'create')
        self.mox.StubOutWithMock(server_models.ServerRole.objects, 'filter')
        self.mox.StubOutWithMock(server_models.ServerAttribute.objects,
                                 'create')
        self.mox.StubOutWithMock(server_models.ServerAttribute.objects,
                                 'filter')
        self.mox.StubOutWithMock(utils, 'normalize_hostname')


    def testCreateServerSuccess(self):
        """Test create method can create a server successfully.
        """
        utils.normalize_hostname(self.BACKUP_DRONE.hostname)
        server_models.Server.objects.get(
                hostname=self.BACKUP_DRONE.hostname
                ).AndRaise(django.core.exceptions.ObjectDoesNotExist)
        server_models.Server.objects.create(
                hostname=mox.IgnoreArg(), status=mox.IgnoreArg(),
                date_created=mox.IgnoreArg(), note=mox.IgnoreArg()
                ).AndReturn(self.BACKUP_DRONE)
        server_models.ServerRole.objects.create(
                server=mox.IgnoreArg(), role=server_models.ServerRole.ROLE.DRONE
                ).AndReturn(self.DRONE_ROLE)
        self.mox.ReplayAll()
        drone = server_manager.create(hostname=self.BACKUP_DRONE.hostname,
                                      role=server_models.ServerRole.ROLE.DRONE)


    def testAddRoleToBackupSuccess(self):
        """Test manager can add a role to a backup server successfully.

        Confirm that database call is made, and no action is taken, e.g.,
        restart scheduler to activate a new devserver.
        """
        server_models.validate(role=server_models.ServerRole.ROLE.DEVSERVER)
        server_models.ServerRole.objects.filter(
                server=self.BACKUP_DRONE,
                role=server_models.ServerRole.ROLE.DEVSERVER).AndReturn(None)
        server_models.ServerRole.objects.create(
                server=mox.IgnoreArg(),
                role=server_models.ServerRole.ROLE.DEVSERVER
                ).AndReturn(self.DRONE_ROLE)
        self.mox.ReplayAll()
        server_manager._add_role(server=self.BACKUP_DRONE,
                                 role=server_models.ServerRole.ROLE.DEVSERVER)


    def testAddRoleToBackupFail_RoleAlreadyExists(self):
        """Test manager fails to add a role to a backup server if server already
        has the given role.
        """
        server_models.validate(role=server_models.ServerRole.ROLE.DRONE)
        server_models.ServerRole.objects.filter(
                server=self.BACKUP_DRONE,
                role=server_models.ServerRole.ROLE.DRONE
                ).AndReturn([self.DRONE_ROLE])
        self.mox.ReplayAll()
        self.assertRaises(server_manager.ServerActionError,
                          server_manager._add_role,
                          server=self.BACKUP_DRONE,
                          role=server_models.ServerRole.ROLE.DRONE)


    def testDeleteRoleFromBackupSuccess(self):
        """Test manager can delete a role from a backup server successfully.

        Confirm that database call is made, and no action is taken, e.g.,
        restart scheduler to delete an existing devserver.
        """
        server_models.validate(role=server_models.ServerRole.ROLE.DRONE)
        server_models.ServerRole.objects.filter(
                server=self.BACKUP_DRONE,
                role=server_models.ServerRole.ROLE.DRONE
                ).AndReturn([self.DRONE_ROLE])
        self.mox.ReplayAll()
        server_manager._delete_role(server=self.BACKUP_DRONE,
                                    role=server_models.ServerRole.ROLE.DRONE)


    def testDeleteRoleFromBackupFail_RoleNotExist(self):
        """Test manager fails to delete a role from a backup server if the
        server does not have the given role.
        """
        server_models.validate(role=server_models.ServerRole.ROLE.DEVSERVER)
        server_models.ServerRole.objects.filter(
                server=self.BACKUP_DRONE,
                role=server_models.ServerRole.ROLE.DEVSERVER
                ).AndReturn(None)
        self.mox.ReplayAll()
        self.assertRaises(server_manager.ServerActionError,
                          server_manager._delete_role, server=self.BACKUP_DRONE,
                          role=server_models.ServerRole.ROLE.DEVSERVER)


    def testChangeStatusSuccess_BackupToPrimary(self):
        """Test manager can change the status of a backup server to primary.
        """
        # TODO(dshi): After _apply_action is implemented, this unittest needs
        # to be updated to verify various actions being taken to put a server
        # in primary status, e.g., start scheduler for scheduler server.
        server_models.validate(status=server_models.Server.STATUS.PRIMARY)
        self.mox.StubOutWithMock(self.BACKUP_DRONE.roles, 'filter')
        self.BACKUP_DRONE.roles.filter(
                role__in=server_models.ServerRole.ROLES_REQUIRE_UNIQUE_INSTANCE
                ).AndReturn(None)
        self.mox.ReplayAll()
        server_manager._change_status(
                server=self.BACKUP_DRONE,
                status=server_models.Server.STATUS.PRIMARY)


    def testChangeStatusSuccess_PrimaryToBackup(self):
        """Test manager can change the status of a primary server to backup.
        """
        server_models.validate(status=server_models.Server.STATUS.BACKUP)
        self.mox.StubOutWithMock(self.PRIMARY_DRONE.roles, 'filter')
        self.PRIMARY_DRONE.roles.filter(
                role__in=server_models.ServerRole.ROLES_REQUIRE_UNIQUE_INSTANCE
                ).AndReturn(None)
        self.mox.ReplayAll()
        server_manager._change_status(
                server=self.PRIMARY_DRONE,
                status=server_models.Server.STATUS.BACKUP)


    def testChangeStatusFail_StatusNoChange(self):
        """Test manager cannot change the status of a server with the same
        status.
        """
        server_models.validate(status=server_models.Server.STATUS.BACKUP)
        self.mox.ReplayAll()
        self.assertRaises(server_manager.ServerActionError,
                          server_manager._change_status,
                          server=self.BACKUP_DRONE,
                          status=server_models.Server.STATUS.BACKUP)


    def testChangeStatusFail_UniqueInstance(self):
        """Test manager cannot change the status of a server from backup to
        primary if there is already a primary exists for role doesn't allow
        multiple instances.
        """
        server_models.validate(status=server_models.Server.STATUS.PRIMARY)
        self.mox.StubOutWithMock(self.BACKUP_SCHEDULER.roles, 'filter')
        self.BACKUP_SCHEDULER.roles.filter(
                role__in=server_models.ServerRole.ROLES_REQUIRE_UNIQUE_INSTANCE
                ).AndReturn(QueriableList([self.SCHEDULER_ROLE]))
        server_models.Server.objects.filter(
                roles__role=self.SCHEDULER_ROLE.role,
                status=server_models.Server.STATUS.PRIMARY
                ).AndReturn(QueriableList([self.PRIMARY_SCHEDULER]))
        self.mox.ReplayAll()
        self.assertRaises(server_manager.ServerActionError,
                          server_manager._change_status,
                          server=self.BACKUP_SCHEDULER,
                          status=server_models.Server.STATUS.PRIMARY)


if '__main__':
    unittest.main()
