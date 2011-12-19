#!/usr/bin/python

# Copyright (c) 2011 The Chromium OS Authors. All rights reserved.
# Use of this source code is governed by a BSD-style license that can be
# found in the LICENSE file.

import common
import mox
import unittest
from autotest_lib.client.common_lib.test_utils import mock
from autotest_lib.frontend import setup_django_environment
from autotest_lib.frontend import setup_test_environment
from autotest_lib.frontend.afe import models
from autotest_lib.scheduler import host_scheduler, metahost_scheduler
from autotest_lib.scheduler import scheduler_models


class SiteHostSchedulerTest(mox.MoxTestBase):
    def setUp(self):
        super(SiteHostSchedulerTest, self).setUp()
        self.god = mock.mock_god()
        self.scheduling_utility = host_scheduler.HostScheduler(db=None)

        # Stub out fake queue entry
        self.queue_entry = self.god.create_mock_class(
                models.HostQueueEntry, 'entry')
        self.queue_entry.set_host = lambda h: ()

        # Stub out the scheduler methods we don't care about.
        self.scheduler = metahost_scheduler.get_metahost_schedulers()[0]
        self.mox.StubOutWithMock(host_scheduler.HostScheduler,
                                 'is_host_usable')
        self.mox.StubOutWithMock(host_scheduler.HostScheduler,
                                 'ineligible_hosts_for_entry')
        self.mox.StubOutWithMock(host_scheduler.HostScheduler,
                                 'is_host_eligible_for_job')
        self.mox.StubOutWithMock(host_scheduler.HostScheduler, 'pop_host')


    def test_hosts_in_label_simple(self):
        """Tests that we can schedule a queue_entry with a simple label.

        Tests the normal case with only one label field.
        """
        hosts = ('host1', 'host2')
        self.queue_entry.meta_host = 'platform_Fake1'
        self.scheduling_utility._label_hosts = {}
        self.scheduling_utility._label_hosts['platform_Fake1'] = [hosts[0]]
        self.scheduling_utility._label_hosts['platform_Fake2'] = [hosts[1]]

        self.scheduling_utility.is_host_usable('host1').AndReturn(True)
        self.scheduling_utility.ineligible_hosts_for_entry(
                self.queue_entry).AndReturn(())
        self.scheduling_utility.is_host_eligible_for_job(
                'host1', self.queue_entry).AndReturn(True)
        self.scheduling_utility.pop_host('host1')
        self.queue_entry.set_host('host1')

        self.mox.ReplayAll()
        self.scheduler.schedule_metahost(self.queue_entry,
                                         self.scheduling_utility)
        self.mox.VerifyAll()


    def test_hosts_in_label_complex(self):
        """Tests that we can schedule a queue_entry with a complex label.

        This test has two labels where only 1 host meets both requirements.
        """
        hosts = ['host1', 'host2']
        self.queue_entry.meta_host = 'platform_Fake1+has_awesome_card'
        self.scheduling_utility._label_hosts = {}
        self.scheduling_utility._label_hosts['platform_Fake1'] = set(hosts)
        self.scheduling_utility._label_hosts['has_awesome_card'] = set(
                [hosts[1]])
        self.scheduling_utility._label_hosts['has_other_card'] = set([hosts[0]])

        self.scheduling_utility.is_host_usable('host2').AndReturn(True)
        self.scheduling_utility.ineligible_hosts_for_entry(
                self.queue_entry).AndReturn(())
        self.scheduling_utility.is_host_eligible_for_job(
                'host2', self.queue_entry).AndReturn(True)
        self.scheduling_utility.pop_host('host2')
        self.queue_entry.set_host('host2')

        self.mox.ReplayAll()
        self.scheduler.schedule_metahost(self.queue_entry,
                                         self.scheduling_utility)
        self.mox.VerifyAll()



if __name__ == '__main__':
    unittest.main()
