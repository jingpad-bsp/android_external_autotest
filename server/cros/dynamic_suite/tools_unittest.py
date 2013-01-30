#!/usr/bin/python
#
# Copyright (c) 2012 The Chromium OS Authors. All rights reserved.
# Use of this source code is governed by a BSD-style license that can be
# found in the LICENSE file.

"""Unit tests for server/cros/dynamic_suite/tools.py."""

import mox

from autotest_lib.client.common_lib import error
from autotest_lib.server.cros.dynamic_suite.comparitors import AllInHostList
from autotest_lib.server.cros.dynamic_suite.fakes import FakeHost
from autotest_lib.server.cros.dynamic_suite.host_spec import HostSpec
from autotest_lib.server.cros.dynamic_suite import host_spec
from autotest_lib.server.cros.dynamic_suite import tools
from autotest_lib.server.cros.dynamic_suite.reimager import OsReimager
from autotest_lib.server import frontend


class DynamicSuiteToolsTest(mox.MoxTestBase):
    """Unit tests for dynamic_suite tools module methods.

    @var _BOARD: fake board to reimage
    """

    _BOARD = 'board'
    _DEPENDENCIES = {'test1': ['label1'], 'test2': ['label2']}
    _POOL = 'bvt'

    def setUp(self):
        super(DynamicSuiteToolsTest, self).setUp()
        self.afe = self.mox.CreateMock(frontend.AFE)
        self.tko = self.mox.CreateMock(frontend.TKO)
        self.reimager = OsReimager('', self._BOARD, afe=self.afe, tko=self.tko)
        # Having these ordered by complexity is important!
        host_spec_list = [HostSpec([self._BOARD, self._POOL])]
        for dep_list in self._DEPENDENCIES.itervalues():
            host_spec_list.append(
                HostSpec([self._BOARD, self._POOL], dep_list))
        self.specs = host_spec.order_by_complexity(host_spec_list)

    def testInjectVars(self):
        """Should inject dict of varibles into provided strings."""
        def find_all_in(d, s):
            """Returns true if all key-value pairs in |d| are printed in |s|."""
            for k, v in d.iteritems():
                if isinstance(v, str):
                    if "%s='%s'\n" % (k, v) not in s:
                        return False
                else:
                    if "%s=%r\n" % (k, v) not in s:
                        return False
            return True

        v = {'v1': 'one', 'v2': 'two', 'v3': None, 'v4': False, 'v5': 5}
        self.assertTrue(find_all_in(v, tools.inject_vars(v, '')))
        self.assertTrue(find_all_in(v, tools.inject_vars(v, 'ctrl')))


    def testIncorrectlyLocked(self):
        """Should detect hosts locked by random users."""
        host = FakeHost(locked=True, locked_by='some guy')
        self.assertTrue(tools.incorrectly_locked(host))


    def testNotIncorrectlyLocked(self):
        """Should accept hosts locked by the infrastructure."""
        infra_user = 'an infra user'
        self.mox.StubOutWithMock(tools, 'infrastructure_user')
        tools.infrastructure_user().AndReturn(infra_user)
        self.mox.ReplayAll()
        host = FakeHost(locked=True, locked_by=infra_user)
        self.assertFalse(tools.incorrectly_locked(host))


    def testEnsureEnoughHosts(self):
        """At least one living host for each list; enough total."""
        self.mox.StubOutWithMock(tools, 'get_random_best_host')

        host_lists = [[FakeHost('h1')], [FakeHost('h2')], [FakeHost('h3')]]
        for hosts in host_lists:
            tools.get_random_best_host(
                self.reimager._afe,
                AllInHostList(hosts),
                True).InAnyOrder('random').AndReturn(hosts[-1])
        self.mox.ReplayAll()

        hosts_per_spec = dict(zip(self.specs, host_lists))
        self.reimager._choose_hosts(hosts_per_spec, len(self.specs))


    def testNoticeZeroHosts(self):
        """Should notice zero hosts for some unique spec, but continue."""
        self.mox.StubOutWithMock(tools, 'get_random_best_host')

        host_lists = [[], [FakeHost('h1')], [FakeHost('h2')]]
        for hosts in host_lists[1:]:
            tools.get_random_best_host(
                self.reimager._afe,
                AllInHostList(hosts),
                True).InAnyOrder('random').AndReturn(hosts[-1])
        # Expect call for the spec with no hosts.
        tools.get_random_best_host(
            self.reimager._afe, [], True).InAnyOrder('random').AndReturn(None)
        # Now, expect an attempt to fill out the list with 'simplest' hosts.
        tools.get_random_best_host(
            self.reimager._afe, [], True).MultipleTimes().AndReturn(None)
        self.mox.ReplayAll()

        hosts_per_spec = dict(zip(self.specs, host_lists))
        explicit_group = self.reimager._choose_hosts(hosts_per_spec,
                                                     len(self.specs))
        self.assertTrue(self.specs[0] in explicit_group.unsatisfied_specs,
                        '%r seems to have been satisfied?' % self.specs[0])


    def testTolerateZeroHostsForSpecThatIsASubset(self):
        """Should tolerate zero hosts for some subsumed spec, but continue."""
        self.mox.StubOutWithMock(tools, 'get_random_best_host')

        host_lists = [[FakeHost('h1')], [FakeHost('h2')], []]
        for hosts in host_lists[:-1]:
            tools.get_random_best_host(
                self.reimager._afe,
                AllInHostList(hosts),
                True).InAnyOrder('random').AndReturn(hosts[-1])
        # Expect call for the spec with no hosts.
        tools.get_random_best_host(
            self.reimager._afe, [], True).InAnyOrder('random').AndReturn(None)
        # Now, expect an attempt to fill out the list with 'simplest' hosts.
        tools.get_random_best_host(
            self.reimager._afe, [], True).MultipleTimes().AndReturn(None)
        self.mox.ReplayAll()

        hosts_per_spec = dict(zip(self.specs, host_lists))
        explicit_group = self.reimager._choose_hosts(hosts_per_spec,
                                                     len(self.specs))
        self.assertFalse(
            explicit_group.unsatisfied_specs,
            '%r should be empty!' % explicit_group.unsatisfied_specs)


    def testFailZeroHostsTotal(self):
        """Should fail on zero hosts for all specs."""
        self.mox.StubOutWithMock(tools, 'get_random_best_host')
        tools.get_random_best_host(
            self.reimager._afe,
            mox.IgnoreArg(),
            True).MultipleTimes().AndReturn(None)
        self.mox.ReplayAll()

        hosts_per_spec = dict([(spec, []) for spec in self.specs])
        self.assertRaises(error.NoHostsException,
                          self.reimager._choose_hosts,
                          hosts_per_spec, len(self.specs))


    def testTolerateTooFewHosts(self):
        """Should tolerate having < num hosts, but one per given specs."""
        self.mox.StubOutWithMock(tools, 'get_random_best_host')

        host_lists = [[FakeHost('h1')], [FakeHost('h2')], [FakeHost('h3')]]
        for hosts in host_lists:
            tools.get_random_best_host(
                self.reimager._afe,
                AllInHostList(hosts),
                True).InAnyOrder('random').AndReturn(hosts[-1])
        tools.get_random_best_host(self.reimager._afe, [], True).AndReturn(None)
        self.mox.ReplayAll()

        hosts_per_spec = dict(zip(self.specs, host_lists))
        self.reimager._choose_hosts(hosts_per_spec, len(self.specs) + 1)


    def testSubsumeTrivialHostSpec(self):
        """Should tolerate num hosts < host specs, if we have a trivial spec."""
        self.mox.StubOutWithMock(tools, 'get_random_best_host')
        num = len(self.specs) - 1

        host_lists = [[FakeHost('h1')], [FakeHost('h2')], [FakeHost('h3')]]
        hosts_per_spec = dict(zip(self.specs, host_lists))

        for spec, hosts in hosts_per_spec.iteritems():
            if spec.is_trivial:
                continue
            tools.get_random_best_host(
                self.reimager._afe,
                AllInHostList(hosts),
                True).InAnyOrder('random').AndReturn(hosts[-1])
        self.mox.ReplayAll()

        hosts = self.reimager._choose_hosts(hosts_per_spec, num)
        self.assertEquals(num, hosts.size())


    def testNumOneStillGetDownToTrivialHostSpec(self):
        """Still run tests, even if we can only satisfy trivial spec."""
        self.mox.StubOutWithMock(tools, 'get_random_best_host')
        num = 1

        host_lists = [[FakeHost('h1')], [FakeHost('h2')], [FakeHost('h3')]]
        hosts_per_spec = dict(zip(self.specs, host_lists))

        for spec, hosts in hosts_per_spec.iteritems():
            if spec.is_trivial:
                tools.get_random_best_host(
                    self.reimager._afe,
                    AllInHostList(hosts),
                    True).InAnyOrder('random').AndReturn(hosts[-1])
            else:
                tools.get_random_best_host(
                    self.reimager._afe,
                    AllInHostList(hosts),
                    True).InAnyOrder('random').AndReturn([])
        self.mox.ReplayAll()

        hosts = self.reimager._choose_hosts(hosts_per_spec, num)
        self.assertEquals(num, hosts.size())


    def testRandomBestHostReadyAvailable(self):
        """Should return one of the 'Ready' hosts."""
        ready = [FakeHost('h3'), FakeHost('h4')]
        hosts = [FakeHost('h1', status='Running'),
                 FakeHost('h2', locked=True, locked_by='some_guy')]
        hosts.extend(ready)
        hostnames = [host.hostname for host in hosts]
        self.afe.get_hosts(
            hostnames=mox.SameElementsAs(hostnames)).AndReturn(hosts)
        self.mox.ReplayAll()
        self.assertTrue(tools.get_random_best_host(self.reimager._afe,
                                                   hosts) in ready)


    def testRandomBestHostNoneUsable(self):
        """Should fail on zero usable hosts."""
        hosts = [FakeHost(status='Repairing'),
                 FakeHost(locked=True, locked_by='some_guy')]
        hostnames = [host.hostname for host in hosts]
        self.afe.get_hosts(
            hostnames=mox.SameElementsAs(hostnames)).AndReturn(hosts)
        self.mox.ReplayAll()
        self.assertEquals(None, tools.get_random_best_host(self.reimager._afe,
                                                           hosts))


    def testRandomBestHostAllowUnusable(self):
        """Should find zero usable hosts, but use them anyhow."""
        hosts = [FakeHost(status='Repairing'),
                 FakeHost(locked=True, locked_by='some_guy')]
        hostnames = [host.hostname for host in hosts]
        self.afe.get_hosts(
            hostnames=mox.SameElementsAs(hostnames)).AndReturn(hosts)
        self.mox.ReplayAll()
        self.assertTrue(
            tools.get_random_best_host(self.reimager._afe, hosts, False)
            in hosts)


    def testRandomBestHostRunningAvailable(self):
        """Should return the correctly locked 'Running' host."""
        user = 'an infra user'
        self.mox.StubOutWithMock(tools, 'infrastructure_user')
        tools.infrastructure_user().MultipleTimes().AndReturn(user)

        running = FakeHost('h1', status='Running', locked=True, locked_by=user)
        hosts = [FakeHost('h2', status='Running', locked=True, locked_by='foo'),
                 FakeHost('h3', status='Repair Failed')]
        hosts.append(running)
        hostnames = [host.hostname for host in hosts]
        self.afe.get_hosts(
            hostnames=mox.SameElementsAs(hostnames)).AndReturn(hosts)
        self.mox.ReplayAll()
        self.assertEquals(running, tools.get_random_best_host(
            self.reimager._afe, hosts))


    def testRandomBestHostCleaningAvailable(self):
        """Should return the 'Cleaning' host."""
        cleaning = FakeHost('h1', status='Cleaning')
        hosts = [FakeHost('h2', status='Ready', locked=True, locked_by='foo'),
                 FakeHost('h3', status='Repair Failed')]
        hosts.append(cleaning)
        hostnames = [host.hostname for host in hosts]
        self.afe.get_hosts(
            hostnames=mox.SameElementsAs(hostnames)).AndReturn(hosts)
        self.mox.ReplayAll()
        self.assertEquals(cleaning, tools.get_random_best_host(
            self.reimager._afe, hosts))


    def testChooseHostsFromSpecsAndHosts(self):
        """Should choose N hosts from per-spec host lists."""
        expected = [FakeHost('h1'), FakeHost('h3'), FakeHost('h4')]
        host_lists = [[FakeHost('h6'), expected[0]],
                      [FakeHost('h2'), expected[1]],
                      [expected[0], FakeHost('h2'), expected[2]]]
        hosts_per_spec = dict(zip(self.specs, host_lists))

        self.mox.StubOutWithMock(tools, 'get_random_best_host')
        for hosts in host_lists:
            tools.get_random_best_host(
                self.reimager._afe,
                AllInHostList(hosts),
                True).InAnyOrder('random').AndReturn(hosts[-1])

        self.mox.ReplayAll()

        to_use = self.reimager._choose_hosts(hosts_per_spec, len(self.specs))
        self.assertEquals(to_use.size(), len(self.specs))
        for expected_host in expected:
            self.assertTrue(to_use.contains_host(expected_host))


    def testChooseExtraHostsFromSpecsAndHosts(self):
        """Should choose N hosts from per-spec host lists, plus one extra."""
        expected = [FakeHost('h1'), FakeHost('h3'), FakeHost('h4')]
        extra_expected = FakeHost('h5')
        host_lists = [[FakeHost('h6'), expected[0]],
                      [FakeHost('h2'), expected[1]],
                      [extra_expected, FakeHost('h2'), expected[2]]]
        hosts_per_spec = dict(zip(self.specs, host_lists))

        self.mox.StubOutWithMock(tools, 'get_random_best_host')
        for hosts in host_lists:
            tools.get_random_best_host(
                self.reimager._afe,
                AllInHostList(hosts),
                True).InAnyOrder('random').AndReturn(hosts[-1])

        # self.specs ordered by complexity, so -1st entry is least complex.
        tools.get_random_best_host(
            self.reimager._afe,
            AllInHostList(hosts_per_spec[self.specs[-1]]),
            True).InAnyOrder('random').AndReturn(extra_expected)

        self.mox.ReplayAll()

        to_use = self.reimager._choose_hosts(hosts_per_spec,
                                             len(self.specs) + 1)
        self.assertEquals(to_use.size(), len(self.specs) + 1)
        for expected_host in expected:
            self.assertTrue(to_use.contains_host(expected_host))
        self.assertTrue(to_use.contains_host(extra_expected))


    def testChooseHostsFromSpecsAndHostsFallShort(self):
        """Should choose N hosts from per-spec host lists, plus none extra."""
        expected = [FakeHost('h1'), FakeHost('h3'), FakeHost('h4')]
        host_lists = [[FakeHost('h6'), expected[0]],
                      [FakeHost('h2'), expected[1]],
                      [expected[0], FakeHost('h2'), expected[2]]]
        hosts_per_spec = dict(zip(self.specs, host_lists))

        self.mox.StubOutWithMock(tools, 'get_random_best_host')
        for hosts in host_lists:
            tools.get_random_best_host(
                self.reimager._afe,
                AllInHostList(hosts),
                True).InAnyOrder('random').AndReturn(hosts[-1])

        # self.specs ordered by complexity, so -1st entry is least complex.
        tools.get_random_best_host(
            self.reimager._afe,
            AllInHostList(hosts_per_spec[self.specs[-1]]),
            True).InAnyOrder('random').AndReturn(None)

        self.mox.ReplayAll()

        to_use = self.reimager._choose_hosts(hosts_per_spec,
                                             len(self.specs) + 1)
        self.assertEquals(to_use.size(), len(self.specs))
        for expected_host in expected:
            self.assertTrue(to_use.contains_host(expected_host))


    def testChooseHostsFromSpecsAndHostsCannotSatisfy(self):
        """Should try to choose N hosts from per-spec host lists, but fail."""
        hosts_per_spec = dict([(spec, []) for spec in self.specs])
        self.mox.StubOutWithMock(tools, 'get_random_best_host')
        tools.get_random_best_host(
            self.reimager._afe,
            mox.IgnoreArg(), True).MultipleTimes().AndReturn(None)
        self.mox.ReplayAll()

        self.assertRaises(error.NoHostsException,
                          self.reimager._choose_hosts,
                          hosts_per_spec, len(self.specs))
