# Copyright (c) 2014 The Chromium OS Authors. All rights reserved.
# Use of this source code is governed by a BSD-style license that can be
# found in the LICENSE file.

import mox

import common

from autotest_lib.frontend import setup_django_environment
from autotest_lib.frontend.afe import frontend_test_utils
from autotest_lib.frontend.afe import models
from autotest_lib.client.common_lib import error
from autotest_lib.client.common_lib import global_config
from autotest_lib.server import frontend
from autotest_lib.shard import shard_client


class ShardClientTest(mox.MoxTestBase,
                      frontend_test_utils.FrontendTestMixin):
    """Unit tests for functions in shard_client.py"""

    def setUp(self):
        super(ShardClientTest, self).setUp()
        self._frontend_common_setup(fill_data=False)


    def setupMocks(self):
        self.mox.StubOutClassWithMocks(frontend, 'AFE')
        self.afe = frontend.AFE(server=mox.IgnoreArg())


    def tearDown(self):
        self._frontend_common_teardown()

        # Without this global_config will keep state over test cases
        global_config.global_config.reset_config_values()


    def _get_sample_serialized_host(self):
        return {'aclgroup_set': [],
                'dirty': True,
                'hostattribute_set': [],
                'hostname': u'host1',
                u'id': 2,
                'invalid': False,
                'labels': [],
                'leased': True,
                'lock_time': None,
                'locked': False,
                'protection': 0,
                'shard': None,
                'status': u'Ready',
                'synch_id': None}


    def testHeartbeat(self):
        """Trigger heartbeat, verify RPCs and persisting of the responses."""
        self.setupMocks()

        global_config.global_config.override_config_value(
                'SHARD', 'is_slave_shard', 'True')
        global_config.global_config.override_config_value(
                'SHARD', 'shard_hostname', 'host1')

        self.afe.run(
            'shard_heartbeat', shard_hostname='host1',
            ).AndReturn({
                'hosts': [self._get_sample_serialized_host()],
                'jobs': [],
            })
        modified_sample_host = self._get_sample_serialized_host()
        modified_sample_host['hostname'] = 'host2'
        self.afe.run(
            'shard_heartbeat', shard_hostname='host1',
            ).AndReturn({
                'hosts': [modified_sample_host],
                'jobs': [],
            })

        self.mox.ReplayAll()
        sut = shard_client.get_shard_client()

        sut.do_heartbeat()

        # Check if dummy object was saved to DB
        host = models.Host.objects.get(id=2)
        self.assertEqual(host.hostname, 'host1')

        sut.do_heartbeat()

        host = models.Host.objects.get(id=2)
        self.assertEqual(host.hostname, 'host1')

        self.mox.VerifyAll()


    def testHeartbeatNoShardMode(self):
        """Ensure an exception is thrown when run on a non-shard machine."""
        global_config.global_config.override_config_value(
                'SHARD', 'is_slave_shard', 'False')
        self.mox.ReplayAll()

        self.assertRaises(error.HeartbeatOnlyAllowedInShardModeException,
                          shard_client.get_shard_client)

        self.mox.VerifyAll()


    def testLoop(self):
        """Test looping over heartbeats and aborting that loop works."""
        self.setupMocks()

        global_config.global_config.override_config_value(
                'SHARD', 'is_slave_shard', 'True')
        global_config.global_config.override_config_value(
                'SHARD', 'heartbeat_pause_sec', '0.01')
        global_config.global_config.override_config_value(
                'SHARD', 'shard_hostname', 'host1')

        self.afe.run(
            'shard_heartbeat', shard_hostname='host1',
            ).AndReturn({
                'hosts': [],
                'jobs': [],
            })

        sut = None

        def shutdown_sut(*args, **kwargs):
            sut.shutdown()

        self.afe.run(
            'shard_heartbeat', shard_hostname='host1',
            ).WithSideEffects(shutdown_sut).AndReturn({
                'hosts': [],
                'jobs': [],
            })


        self.mox.ReplayAll()
        sut = shard_client.get_shard_client()
        sut.loop()

        self.mox.VerifyAll()
