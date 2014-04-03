# Copyright (c) 2014 The Chromium OS Authors. All rights reserved.
# Use of this source code is governed by a BSD-style license that can be
# found in the LICENSE file.

import mock
import unittest

import common
from autotest_lib.frontend import setup_django_lite_environment
from autotest_lib.frontend.afe import frontend_test_utils
from autotest_lib.frontend.afe import rdb_model_extensions as rdb_models
from autotest_lib.scheduler import rdb_integration_tests
from autotest_lib.scheduler import rdb
from autotest_lib.scheduler import rdb_hosts
from autotest_lib.scheduler import rdb_requests
from autotest_lib.scheduler import rdb_utils


from django.core import exceptions as django_exceptions
from django.db.models import fields


class FakeHost(rdb_hosts.RDBHost):
    """Fake host to use in unittests."""

    def __init__(self, hostname, host_id, **kwargs):
        kwargs.update({'hostname': hostname, 'id': host_id})
        kwargs = rdb_models.AbstractHostModel.provide_default_values(
                kwargs)
        super(FakeHost, self).__init__(**kwargs)


class RDBBaseRequestHandlerTests(unittest.TestCase):
    """Base Request Handler Unittests."""

    def setUp(self):
        self.handler = rdb.BaseHostRequestHandler()
        self.handler.host_query_manager = mock.MagicMock()
        self.update_manager = rdb_requests.BaseHostRequestManager(
                rdb_requests.UpdateHostRequest, rdb.update_hosts)
        self.get_hosts_manager = rdb_requests.BaseHostRequestManager(
                rdb_requests.HostRequest, rdb.get_hosts)


    def tearDown(self):
        self.handler.host_query_manager.reset_mock()


    def testResponseMapUpdate(self):
        """Test response map behaviour.

        Test that either adding an empty response against a request, or 2
        responses for the same request will raise an exception.
        """
        self.get_hosts_manager.add_request(host_id=1)
        request = self.get_hosts_manager.request_queue[0]
        response = []
        self.assertRaises(
                rdb_utils.RDBException, self.handler.update_response_map,
                *(request, response))
        response.append(FakeHost(hostname='host', host_id=1))
        self.handler.update_response_map(request, response)
        self.assertRaises(
                rdb_utils.RDBException, self.handler.update_response_map,
                *(request, response))


    def testBatchGetHosts(self):
        """Test getting hosts.

        Verify that:
            1. We actually call get_hosts on the query_manager for a
                batched_get_hosts request.
            2. The hosts returned are matched up correctly with requests,
                and each request gets exactly one response.
            3. The hosts returned have all the fields needed to create an
                RDBClientHostWrapper, in spite of having gone through the
                to_wire process of serialization in get_response.
        """
        fake_hosts = []
        for host_id in range(1, 4):
            self.get_hosts_manager.add_request(host_id=host_id)
            fake_hosts.append(FakeHost('host%s'%host_id, host_id))
        self.handler.host_query_manager.get_hosts = mock.MagicMock(
                return_value=fake_hosts)
        self.handler.batch_get_hosts(self.get_hosts_manager.request_queue)
        for request, hosts in self.handler.get_response().iteritems():
            self.assertTrue(len(hosts) == 1)
            client_host = rdb_hosts.RDBClientHostWrapper(**hosts[0])
            self.assertTrue(request.host_id == client_host.id)


    def testSingleUpdateRequest(self):
        """Test that a single host update request hits the query manager."""
        payload = {'status': 'Ready'}
        host_id = 10
        self.update_manager.add_request(host_id=host_id, payload=payload)
        self.handler.update_hosts(self.update_manager.request_queue)
        self.handler.host_query_manager.update_hosts.assert_called_once_with(
                [host_id], **payload)


    def testDedupingSameHostRequests(self):
        """Test same host 2 updates deduping."""
        payload_1 = {'status': 'Ready'}
        payload_2 = {'locked': True}
        host_id = 10
        self.update_manager.add_request(host_id=host_id, payload=payload_1)
        self.update_manager.add_request(host_id=host_id, payload=payload_2)
        self.handler.update_hosts(self.update_manager.request_queue)
        self.handler.host_query_manager.update_hosts.assert_called_once_with(
                [host_id], **dict(payload_1.items() + payload_2.items()))


    def testLastUpdateWins(self):
        """Test 2 updates to the same row x column."""
        payload_1 = {'status': 'foobar'}
        payload_2 = {'status': 'Ready'}
        host_id = 10
        self.update_manager.add_request(host_id=host_id, payload=payload_1)
        self.update_manager.add_request(host_id=host_id, payload=payload_2)
        self.handler.update_hosts(self.update_manager.request_queue)
        self.handler.host_query_manager.update_hosts.assert_called_once_with(
                [host_id], **payload_2)


    def testDedupingSamePayloadRequests(self):
        """Test same payload for 2 hosts only hits the db once."""
        payload = {'status': 'Ready'}
        host_1_id = 10
        host_2_id = 20
        self.update_manager.add_request(host_id=host_1_id, payload=payload)
        self.update_manager.add_request(host_id=host_2_id, payload=payload)
        self.handler.update_hosts(self.update_manager.request_queue)
        self.handler.host_query_manager.update_hosts.assert_called_once_with(
                [host_1_id, host_2_id], **payload)


    def testUpdateException(self):
        """Test update exception handling.

        1. An exception raised while processing one update shouldn't prevent
            the others.
        2. The exception shold get serialized as a string and returned via the
            response map.
        """
        payload = {'status': 'Ready'}
        exception_msg = 'Bad Field'
        exception_types = [django_exceptions.FieldError,
                           fields.FieldDoesNotExist]
        self.update_manager.add_request(host_id=11, payload=payload)
        self.update_manager.add_request(host_id=10, payload=payload)
        mock_query_manager = self.handler.host_query_manager

        for e, request in zip(
                exception_types, self.update_manager.request_queue):
            mock_query_manager.update_hosts.side_effect = e(exception_msg)
            self.handler.update_hosts([request])

        response = self.handler.get_response()
        for request in self.update_manager.request_queue:
            self.assertTrue(exception_msg in response.get(request))


class QueryManagerTests(unittest.TestCase,
                        frontend_test_utils.FrontendTestMixin):
    """Query Manager Tests."""

    def setUp(self):
        self.db_helper = rdb_integration_tests.DBHelper()
        self._database = self.db_helper.database

        # Runs syncdb setting up initial database conditions
        self._frontend_common_setup()
        self.available_hosts_query_manager = rdb.AvailableHostQueryManager()
        self.all_hosts_query_manager = rdb.BaseHostQueryManager()


    def tearDown(self):
        self._database.disconnect()
        self._frontend_common_teardown()


    def testFindHosts(self):
        """Test finding hosts.

        Tests that we can only find unleased hosts through the
        available_hosts_query_manager.
        """
        deps = set(['a', 'b'])
        acls = set(['a'])
        db_host = self.db_helper.create_host(
                name='h1', deps=deps, acls=acls, leased=1)
        hosts = self.all_hosts_query_manager.find_hosts(
                deps=[lable.id for lable in db_host.labels.all()],
                acls=[aclgroup.id for aclgroup in db_host.aclgroup_set.all()])
        self.assertTrue(type(hosts) == list and len(hosts) == 1)
        hosts = self.available_hosts_query_manager.find_hosts(
                deps=[lable.id for lable in db_host.labels.all()],
                acls=[aclgroup.id for aclgroup in db_host.aclgroup_set.all()])
        # We should get an empty list if there are no matching hosts, not a
        # QuerySet or None.
        self.assertTrue(len(hosts) == 0)


    def testUpdateHosts(self):
        """Test updating hosts.

        Test that we can only update unleased hosts through the
        available_hosts_query_manager.
        """
        deps = set(['a', 'b'])
        acls = set(['a'])
        db_host = self.db_helper.create_host(
                name='h1', deps=deps, acls=acls, leased=1)
        # Confirm that the available_hosts_manager can't see the leased host.
        self.assertTrue(
                len(self.available_hosts_query_manager.get_hosts(
                        [db_host.id])) == 0)

        # Confirm that the available_hosts_manager can't update a leased host.
        # Also confirm that the general query manager Can see the leased host.
        self.available_hosts_query_manager.update_hosts(
                [db_host.id], **{'leased': 0})
        hosts = self.all_hosts_query_manager.get_hosts([db_host.id])
        self.assertTrue(len(hosts) == 1 and hosts[0].leased)

        # Confirm that we can infact update the leased bit on the host.
        self.all_hosts_query_manager.update_hosts(
                [hosts[0].id], **{'leased': 0})
        hosts = self.all_hosts_query_manager.get_hosts([hosts[0].id])
        self.assertTrue(len(hosts) == 1 and not hosts[0].leased)



