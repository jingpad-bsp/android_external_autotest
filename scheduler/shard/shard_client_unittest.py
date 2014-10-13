# Copyright (c) 2014 The Chromium OS Authors. All rights reserved.
# Use of this source code is governed by a BSD-style license that can be
# found in the LICENSE file.

import datetime
import mox

import common

from autotest_lib.frontend import setup_django_environment
from autotest_lib.frontend.afe import frontend_test_utils
from autotest_lib.frontend.afe import models
from autotest_lib.client.common_lib import error
from autotest_lib.client.common_lib import global_config
from autotest_lib.server.cros.dynamic_suite import frontend_wrappers
from autotest_lib.scheduler.shard import shard_client


class ShardClientTest(mox.MoxTestBase,
                      frontend_test_utils.FrontendTestMixin):
    """Unit tests for functions in shard_client.py"""


    GLOBAL_AFE_HOSTNAME = 'foo_autotest'


    def setUp(self):
        super(ShardClientTest, self).setUp()

        global_config.global_config.override_config_value(
                'SHARD', 'global_afe_hostname', self.GLOBAL_AFE_HOSTNAME)

        self._frontend_common_setup(fill_data=False)


    def setupMocks(self):
        self.mox.StubOutClassWithMocks(frontend_wrappers, 'RetryingAFE')
        self.afe = frontend_wrappers.RetryingAFE(
                delay_sec=5, server=self.GLOBAL_AFE_HOSTNAME, timeout_min=5)


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


    def _get_sample_serialized_job(self):
        return {'control_file': u'control',
                'control_type': 2,
                'created_on': datetime.datetime(2008, 1, 1, 0, 0),
                'dependency_labels': [],
                'email_list': u'',
                'hostqueueentry_set': [{'aborted': False,
                                        'active': False,
                                        'complete': False,
                                        'deleted': False,
                                        'execution_subdir': u'',
                                        'finished_on': None,
                                        u'id': 2,
                                        'meta_host': {u'id': 10,
                                                      'invalid': False,
                                                      'kernel_config': u'',
                                                      'name': u'myplatform',
                                                      'only_if_needed': False,
                                                      'platform': True},
                                        'started_on': None,
                                        'status': u'Queued'}],
                u'id': 2,
                'jobkeyval_set': [],
                'max_runtime_hrs': 72,
                'max_runtime_mins': 1440,
                'name': u'test',
                'owner': u'autotest_system',
                'parse_failed_repair': True,
                'priority': 0,
                'reboot_after': 0,
                'reboot_before': 0,
                'run_reset': True,
                'run_verify': False,
                'shard': {'hostname': 'host1',
                          'id': 4},
                'synch_count': 1,
                'test_retry': 0,
                'timeout': 24,
                'timeout_mins': 1440}


    def testHeartbeat(self):
        """Trigger heartbeat, verify RPCs and persisting of the responses."""
        self.setupMocks()

        global_config.global_config.override_config_value(
                'SHARD', 'shard_hostname', 'host1')

        self.afe.run(
            'shard_heartbeat', shard_hostname='host1', jobs=[], hqes=[],
            ).AndReturn({
                'hosts': [self._get_sample_serialized_host()],
                'jobs': [self._get_sample_serialized_job()],
            })
        modified_sample_host = self._get_sample_serialized_host()
        modified_sample_host['hostname'] = 'host2'
        self.afe.run(
            'shard_heartbeat', shard_hostname='host1', jobs=[], hqes=[]
            ).AndReturn({
                'hosts': [modified_sample_host],
                'jobs': [],
            })


        def verify_upload_jobs_and_hqes(name, shard_hostname, jobs, hqes):
            self.assertEqual(len(jobs), 1)
            self.assertEqual(len(hqes), 1)
            job, hqe = jobs[0], hqes[0]
            self.assertEqual(hqe['status'], 'Completed')


        self.afe.run(
            'shard_heartbeat', shard_hostname='host1', jobs=mox.IgnoreArg(),
            hqes=mox.IgnoreArg()
            ).WithSideEffects(verify_upload_jobs_and_hqes).AndReturn({
                'hosts': [],
                'jobs': [],
            })

        self.mox.ReplayAll()
        sut = shard_client.get_shard_client()

        sut.do_heartbeat()

        # Check if dummy object was saved to DB
        host = models.Host.objects.get(id=2)
        self.assertEqual(host.hostname, 'host1')

        sut.do_heartbeat()

        # Ensure it wasn't overwritten
        host = models.Host.objects.get(id=2)
        self.assertEqual(host.hostname, 'host1')

        job = models.Job.objects.all()[0]
        job.shard = None
        job.save()
        hqe = job.hostqueueentry_set.all()[0]
        hqe.status = 'Completed'
        hqe.save()

        sut.do_heartbeat()


        self.mox.VerifyAll()


    def testHeartbeatNoShardMode(self):
        """Ensure an exception is thrown when run on a non-shard machine."""
        self.mox.ReplayAll()

        self.assertRaises(error.HeartbeatOnlyAllowedInShardModeException,
                          shard_client.get_shard_client)

        self.mox.VerifyAll()


    def testLoop(self):
        """Test looping over heartbeats and aborting that loop works."""
        self.setupMocks()

        global_config.global_config.override_config_value(
                'SHARD', 'heartbeat_pause_sec', '0.01')
        global_config.global_config.override_config_value(
                'SHARD', 'shard_hostname', 'host1')

        self.afe.run(
            'shard_heartbeat', shard_hostname='host1', jobs=[], hqes=[]
            ).AndReturn({
                'hosts': [],
                'jobs': [],
            })

        sut = None

        def shutdown_sut(*args, **kwargs):
            sut.shutdown()

        self.afe.run(
            'shard_heartbeat', shard_hostname='host1', jobs=[], hqes=[]
            ).WithSideEffects(shutdown_sut).AndReturn({
                'hosts': [],
                'jobs': [],
            })


        self.mox.ReplayAll()
        sut = shard_client.get_shard_client()
        sut.loop()

        self.mox.VerifyAll()
