#!/usr/bin/python
#
# Copyright (c) 2012 The Chromium OS Authors. All rights reserved.
# Use of this source code is governed by a BSD-style license that can be
# found in the LICENSE file.

"""Unit tests for server/cros/dynamic_suite/reimager.py."""

import mox

from autotest_lib.client.common_lib import base_job, error
from autotest_lib.client.common_lib import global_config
from autotest_lib.client.common_lib.cros import dev_server
from autotest_lib.frontend.afe.json_rpc import proxy
from autotest_lib.server.cros.dynamic_suite import control_file_getter
from autotest_lib.server.cros.dynamic_suite import host_spec
from autotest_lib.server.cros.dynamic_suite import job_status, tools
from autotest_lib.server.cros.dynamic_suite.comparitors import StatusContains
from autotest_lib.server.cros.dynamic_suite.host_spec import ExplicitHostGroup
from autotest_lib.server.cros.dynamic_suite.host_spec import HostGroup
from autotest_lib.server.cros.dynamic_suite.host_spec import HostSpec
from autotest_lib.server.cros.dynamic_suite.host_spec import MetaHostGroup
from autotest_lib.server.cros.dynamic_suite.reimager import OsReimager
from autotest_lib.server.cros.dynamic_suite.fakes import FakeHost, FakeJob
from autotest_lib.server import frontend


class ReimagerTest(mox.MoxTestBase):
    """Unit tests for dynamic_suite Reimager class.

    @var _URL: fake image url
    @var _BUILD: fake build
    @var _NUM: fake number of machines to run on
    @var _BOARD: fake board to reimage
    """


    _DEVSERVER_URL = 'http://nothing:8082'
    _BUILD = 'build'
    _UPDATE_URL = _DEVSERVER_URL + '/update/' + _BUILD
    _URL = '%s/%s'
    _NUM = 4
    _BOARD = 'board'
    _POOL = 'bvt'
    _DEPENDENCIES = {'test1': ['label1'], 'test2': ['label2']}
    _CONFIG = global_config.global_config


    def setUp(self):
        super(ReimagerTest, self).setUp()
        self.afe = self.mox.CreateMock(frontend.AFE)
        self.tko = self.mox.CreateMock(frontend.TKO)
        self.devserver = dev_server.ImageServer(self._DEVSERVER_URL)
        self.reimager = OsReimager('', self._BOARD, afe=self.afe, tko=self.tko)
        # Having these ordered by complexity is important!
        host_spec_list = [HostSpec([self._BOARD, self._POOL])]
        for dep_list in self._DEPENDENCIES.itervalues():
            host_spec_list.append(
                HostSpec([self._BOARD, self._POOL], dep_list))
        self.specs = host_spec.order_by_complexity(host_spec_list)
        self._CONFIG.override_config_value('CROS',
                                           'sharding_factor',
                                           "%d" % self._NUM)


    def check_specs(self, specs, expected):
        """
        Asserts that for each entry x in the list specs, x.labels is
        in the list expected.
        @param specs: A list of specs to be checked.
        @param expected: A list of expected labels values.
        """
        for labels in expected:
            labels.sort()
        for spec in specs:
          self.assertTrue(spec.labels in expected,
                          '%r not in %r' % (spec.labels, expected))


    def testBuildHostSpecs(self):
        """Should uniquify a dict of test deps into a list of host specs."""
        base_expectations = [['label1', 'label2'], ['label1'], []]
        dependencies = {'a': base_expectations[2],
                        'b': sorted(base_expectations[0], reverse=True),
                        'c': base_expectations[1],
                        'd': base_expectations[0],
                        'e': base_expectations[1],
                        }
        per_test_specs = self.reimager._build_host_specs_from_dependencies(
            self._BOARD, None, dependencies)
        self.check_specs(set(per_test_specs.values()),
                         [d + [self._BOARD] for d in base_expectations])

        per_test_specs = self.reimager._build_host_specs_from_dependencies(
            self._BOARD, self._POOL, dependencies)
        self.check_specs(
            set(per_test_specs.values()),
            [d + [self._BOARD, self._POOL] for d in base_expectations])


    def testBuildHostSpecsFromEmptyDict(self):
        """Should tolerate an empty dict of test deps."""
        per_test_specs = self.reimager._build_host_specs_from_dependencies(
            self._BOARD, None, {'':[]})
        specs = set(per_test_specs.values())
        self.assertEquals(len(specs), 1)
        self.assertEquals(specs.pop().labels, [self._BOARD])


    def testEnsureVersionLabelAlreadyExists(self):
        """Should tolerate a label that already exists."""
        name = 'label'
        error = proxy.ValidationError(
            {'name': 'ValidationError',
             'message': '{"name": "This value must be unique"}',
             'traceback': ''},
            'BAD')
        self.afe.create_label(name=name).AndRaise(error)
        self.mox.ReplayAll()
        self.reimager._ensure_version_label(name)


    def testEnsureVersionLabel(self):
        """Should create a label if it doesn't already exist."""
        name = 'label'
        self.afe.create_label(name=name)
        self.mox.ReplayAll()
        self.reimager._ensure_version_label(name)


    def testGatherHostsFromSpecs(self):
        """Get at least one host per spec."""
        host_lists = [['h1'], ['h2', 'h3'], ['h1', 'h2', 'h4']]
        spec_host_pairs = zip(self.specs, host_lists)

        for spec, hosts in spec_host_pairs:
            self.afe.get_hosts(
                multiple_labels=mox.SameElementsAs(spec.labels)
                ).AndReturn(hosts)

        self.mox.ReplayAll()
        self.assertEquals(
            dict(spec_host_pairs),
            self.reimager._gather_hosts_from_host_specs(self.specs))


    def testBuildHostGroupComplex(self):
        """Build a HostGroup from hosts, given a complex set of HostSpec."""
        self.mox.StubOutWithMock(self.reimager, '_choose_hosts')
        self.mox.StubOutWithMock(self.reimager, '_gather_hosts_from_host_specs')

        require_usable_hosts = True
        host_lists = [[FakeHost('h%d' % i)] for i,spec in enumerate(self.specs)]
        hosts_per_spec = dict(zip(self.specs, host_lists))
        host_group = ExplicitHostGroup(hosts_per_spec)

        self.reimager._gather_hosts_from_host_specs(
            self.specs).AndReturn(hosts_per_spec)
        self.reimager._choose_hosts(
            hosts_per_spec,
            len(self.specs),
            require_usable_hosts).AndReturn(host_group)

        self.mox.ReplayAll()
        self.assertEquals(host_group,
                          self.reimager._build_host_group(self.specs,
                                                          len(self.specs),
                                                          require_usable_hosts))


    def testBuildHostGroupComplexContainingTrivial(self):
        """Build a HostGroup, given a complex set of specs, with one trivial."""
        self.mox.StubOutWithMock(self.reimager, '_choose_hosts')
        self.mox.StubOutWithMock(self.reimager, '_gather_hosts_from_host_specs')

        require_usable_hosts = True
        host_lists = [[FakeHost('h%d' % i)] for i,spec in enumerate(self.specs)]
        hosts_per_spec = dict(zip(self.specs, host_lists))
        host_group = ExplicitHostGroup(hosts_per_spec)

        self.reimager._gather_hosts_from_host_specs(
            self.specs).AndReturn(hosts_per_spec)
        self.reimager._choose_hosts(
            hosts_per_spec,
            len(self.specs) - 1,
            require_usable_hosts).AndReturn(host_group)

        self.mox.ReplayAll()
        self.assertEquals(host_group,
                          self.reimager._build_host_group(self.specs,
                                                          len(self.specs) - 1,
                                                          require_usable_hosts))


    def testBuildHostGroupNotEnough(self):
        """Raise if more nontrivial HostSpecs than machines allowed."""
        specs = [HostSpec(['l1'], ['e1']), HostSpec(['21'], ['e1'])]
        self.assertRaises(error.InadequateHostsException,
                          self.reimager._build_host_group,
                          specs,
                          len(specs) - 1,
                          True)


    def testBuildHostGroupSimple(self):
        """Build a HostGroup from labels, given a simple set of HostSpec."""
        spec = self.specs[0]
        host_list = [FakeHost(), FakeHost()]
        self.afe.get_hosts(multiple_labels=spec.labels).AndReturn(host_list)

        host_group = MetaHostGroup(spec.labels, len(host_list))
        self.mox.StubOutWithMock(self.reimager, '_choose_hosts')
        self.mox.ReplayAll()
        self.assertTrue(host_group,
                        self.reimager._build_host_group([spec],
                                                        len(host_list),
                                                        True))


    def testBuildHostGroupSimpleNone(self):
        """Raise when we find no machines to match a simple set of HostSpec."""
        spec = self.specs[0]
        self.afe.get_hosts(multiple_labels=spec.labels).AndReturn([])

        self.mox.StubOutWithMock(self.reimager, '_choose_hosts')
        self.mox.ReplayAll()
        self.assertRaises(error.NoHostsException,
                          self.reimager._build_host_group,
                          [spec],
                          1,
                          True)


    def testScheduleJob(self):
        """Should be able to create a job with the AFE."""
        # Fake out getting the autoupdate control file contents.
        cf_getter = self.mox.CreateMock(control_file_getter.ControlFileGetter)
        cf_getter.get_control_file_contents_by_name('autoupdate').AndReturn('')
        self.reimager._cf_getter = cf_getter

        hosts_per_spec = {HostSpec(['l1']): [FakeHost('h1')],
                          HostSpec(['l2']): [FakeHost('h2')],
                          HostSpec(['l3']): [FakeHost('h4')]}
        hostnames = [h[0].hostname for h in hosts_per_spec.values()]
        self.afe.create_job(
            control_file=mox.And(
                mox.StrContains(self._BUILD),
                mox.StrContains(self._UPDATE_URL)),
            name=mox.StrContains(self._BUILD),
            control_type='Server',
            hosts=mox.SameElementsAs(hostnames),
            priority='Low',
            parent_job_id=None)
        self.mox.ReplayAll()
        self.reimager._schedule_reimage_job(
            {'image_name': self._BUILD},
            ExplicitHostGroup(hosts_per_spec), self.devserver)


    def testPackageUrl(self):
        """Should be able to get the package_url for any build."""
        self._CONFIG.override_config_value('CROS',
                                           'package_url_pattern',
                                           self._URL)
        self.mox.ReplayAll()
        package_url = tools.get_package_url(self._DEVSERVER_URL, self._BUILD)
        self.assertEqual(package_url, self._URL % (self._DEVSERVER_URL,
                                                   self._BUILD))


    def expect_attempt(self, canary_job, statuses, ex=None, check_hosts=True,
                       unsatisfiable_specs=[], doomed_specs=[],
                       tryjob_aborted=False):
        """Sets up |self.reimager| to expect an attempt().

        The return value of attempt() is dictated by the aggregate of the
        status values in |statuses|; if all are GOOD, then attempt() will
        return True.  Otherwise, False -- just like the real call.

        Also stubs out Reimager._clear_build_state(), should the caller wish
        to set an expectation there as well.

        @param canary_job: a FakeJob representing the job we're expecting.
        @param statuses: dict mapping a hostname to its job_status.Status.
                         Will be returned by job_status.gather_per_host_results
        @param ex: if not None, |ex| is raised by get_jobs()
        @param check_hosts: expected check_hosts argument
        @param unsatisfiable_specs: desired host_group.unsatisfiable_specs
        @param doomed_specs: desired host_group.doomed_specs
        @param tryjob_aborted: report that too many tryjobs aborted
        @return a FakeJob configured with appropriate expectations
        """
        self.mox.StubOutWithMock(self.reimager, '_ensure_version_label')
        self.mox.StubOutWithMock(self.reimager, '_build_host_group')
        self.mox.StubOutWithMock(self.reimager, '_schedule_reimage_job_base')
        self.mox.StubOutWithMock(self.reimager, '_clear_build_state')

        self.mox.StubOutWithMock(job_status, 'wait_for_jobs_to_start')
        self.mox.StubOutWithMock(job_status, 'wait_for_and_lock_job_hosts')
        self.mox.StubOutWithMock(job_status, 'gather_job_hostnames')
        self.mox.StubOutWithMock(job_status, 'wait_for_jobs_to_finish')
        self.mox.StubOutWithMock(job_status, 'gather_per_host_results')
        self.mox.StubOutWithMock(job_status, 'check_and_record_reimage_results')
        self.mox.StubOutWithMock(job_status, 'check_job_abort_status')

        self.reimager._ensure_version_label(mox.StrContains(self._BUILD))

        host_group = self.mox.CreateMock(HostGroup)
        host_group.unsatisfied_specs = unsatisfiable_specs
        host_group.doomed_specs = doomed_specs
        self.reimager._build_host_group(
            mox.IgnoreArg(), self._NUM, check_hosts).AndReturn(host_group)
        self.reimager._schedule_reimage_job(
            {'image_name': self._BUILD},
            host_group,
            self.devserver).AndReturn(canary_job)

        job_status.wait_for_jobs_to_start(self.afe, [canary_job],
            start_time=mox.IgnoreArg(),
            wait_timeout_mins=mox.IgnoreArg()).AndReturn(True)

        if ex:
            job_status.wait_for_jobs_to_finish(self.afe,
                                               [canary_job]).AndRaise(ex)
            return
        else:
            job_status.wait_for_jobs_to_finish(self.afe, [canary_job])

            job_status.check_job_abort_status(mox.IgnoreArg(), mox.IgnoreArg()
                ).AndReturn(tryjob_aborted)
            if tryjob_aborted:
                return
            job_status.gather_per_host_results(
                mox.IgnoreArg(), mox.IgnoreArg(), [canary_job],
                mox.StrContains(OsReimager.JOB_NAME)).AndReturn(statuses)

        if statuses:
            ret_val = reduce(lambda v, s: v or s.is_good(),
                             statuses.values(), False)
            job_status.check_and_record_reimage_results(
                statuses, host_group, mox.IgnoreArg()).AndReturn(ret_val)


    def testSuccessfulReimage(self):
        """Should attempt a reimage and record success."""
        canary = FakeJob()
        statuses = {canary.hostnames[0]:
                    job_status.Status('GOOD', canary.hostnames[0])}
        self.expect_attempt(canary, statuses)

        rjob = self.mox.CreateMock(base_job.base_job)
        self.reimager._clear_build_state(mox.StrContains(canary.hostnames[0]))
        self.mox.ReplayAll()

        self.assertTrue(self.reimager.attempt(self._BUILD, self._POOL,
                                              self.devserver,
                                              rjob.record_entry, True,
                                              [], self._DEPENDENCIES))
        self.reimager.clear_reimaged_host_state(self._BUILD)


    def testTryJobAborted(self):
        """Should attempt a reimage that aborts and record ABORT"""
        canary = FakeJob()
        statuses = {canary.hostnames[0]:
                    job_status.Status('GOOD', canary.hostnames[0])}
        self.expect_attempt(canary, statuses, tryjob_aborted=True)

        rjob = self.mox.CreateMock(base_job.base_job)
        rjob.record_entry(StatusContains.CreateFromStrings('START'))
        rjob.record_entry(StatusContains.CreateFromStrings('ABORT'))
        rjob.record_entry(StatusContains.CreateFromStrings('END ABORT'))

        self.mox.ReplayAll()
        self.assertFalse(self.reimager.attempt(self._BUILD, self._POOL,
                                               self.devserver,
                                               rjob.record_entry, True, [],
                                               self._DEPENDENCIES))
        self.reimager.clear_reimaged_host_state(self._BUILD)


    def testSuccessfulReimageByMetahost(self):
        """Should attempt a reimage by metahost and record success."""
        canary = FakeJob()
        statuses = {canary.hostnames[0]: job_status.Status('GOOD',
                                                           canary.hostnames[0])}
        self.expect_attempt(canary, statuses)

        rjob = self.mox.CreateMock(base_job.base_job)
        self.reimager._clear_build_state(mox.StrContains(canary.hostnames[0]))
        self.mox.ReplayAll()
        self.assertTrue(self.reimager.attempt(self._BUILD, self._POOL,
                                              self.devserver,
                                              rjob.record_entry, True, []))
        self.reimager.clear_reimaged_host_state(self._BUILD)


    def testPartialReimage(self):
        """Should attempt a reimage with failing hosts and record success."""
        canary = FakeJob(hostnames=['host1', 'host2'])
        statuses = {
            canary.hostnames[0]: job_status.Status('FAIL', canary.hostnames[0]),
            canary.hostnames[1]: job_status.Status('GOOD', canary.hostnames[1]),
        }
        self.expect_attempt(canary, statuses)

        rjob = self.mox.CreateMock(base_job.base_job)
        comparator = mox.Or(mox.StrContains('host1'), mox.StrContains('host2'))
        self.reimager._clear_build_state(comparator)
        self.reimager._clear_build_state(comparator)
        self.mox.ReplayAll()
        self.assertTrue(self.reimager.attempt(self._BUILD, None,
                                              self.devserver,
                                              rjob.record_entry, True, []))
        self.reimager.clear_reimaged_host_state(self._BUILD)


    def testPartialReimageWithDependencies(self):
        """Attempt a reimage with unsatisfied deps and report tests to skip."""
        canary = FakeJob()
        statuses = {canary.hostnames[0]: job_status.Status('GOOD',
                                                           canary.hostnames[0])}
        bad_test, bad_labels = self._DEPENDENCIES.items()[0]
        bad_spec = HostSpec([self._BOARD, self._POOL], bad_labels)
        self.expect_attempt(canary, statuses, unsatisfiable_specs=[bad_spec])

        rjob = self.mox.CreateMock(base_job.base_job)
        rjob.record_entry(StatusContains.CreateFromStrings('START'))
        rjob.record_entry(StatusContains.CreateFromStrings('TEST_NA', bad_test))
        rjob.record_entry(StatusContains.CreateFromStrings('END TEST_NA'))
        self.reimager._clear_build_state(mox.StrContains(canary.hostnames[0]))
        self.mox.ReplayAll()
        tests_to_skip = []
        self.assertTrue(self.reimager.attempt(self._BUILD, self._POOL,
                                              self.devserver,
                                              rjob.record_entry, True,
                                              tests_to_skip,
                                              self._DEPENDENCIES))
        self.reimager.clear_reimaged_host_state(self._BUILD)
        self.assertTrue(bad_test in tests_to_skip)


    def testPartialFailedReimageAttemptWithDependencies(self):
        """Attempt a reimage, using reimager.attempt, with failing hosts.

        This will not error on unrunnable tests, because it relies on the
        now deprecated dependencies paramater to Reimager.wait, rather than
        using the scheulded_tests parameter."""
        canary = FakeJob(hostnames=['host1', 'host2'])
        statuses = {
            canary.hostnames[0]: job_status.Status('FAIL', canary.hostnames[0]),
            canary.hostnames[1]: job_status.Status('GOOD', canary.hostnames[1]),
        }
        bad_test, bad_labels = self._DEPENDENCIES.items()[0]
        bad_spec = HostSpec([self._BOARD, self._POOL], bad_labels)
        self.expect_attempt(canary, statuses, doomed_specs=[bad_spec])

        rjob = self.mox.CreateMock(base_job.base_job)
        comparator = mox.Or(mox.StrContains(canary.hostnames[0]),
                            mox.StrContains(canary.hostnames[1]))
        self.reimager._clear_build_state(comparator)
        self.reimager._clear_build_state(comparator)
        self.mox.ReplayAll()
        tests_to_skip = []
        self.assertTrue(self.reimager.attempt(self._BUILD, self._POOL,
                                              self.devserver,
                                              rjob.record_entry, True,
                                              tests_to_skip,
                                              self._DEPENDENCIES))
        self.reimager.clear_reimaged_host_state(self._BUILD)
        self.assertEquals(0, len(tests_to_skip))


    def testFailedReimage(self):
        """Should attempt a reimage and record failure."""
        canary = FakeJob()
        statuses = {canary.hostnames[0]: job_status.Status('FAIL',
                                                           canary.hostnames[0])}
        self.expect_attempt(canary, statuses)

        rjob = self.mox.CreateMock(base_job.base_job)
        self.reimager._clear_build_state(mox.StrContains(canary.hostnames[0]))
        self.mox.ReplayAll()
        self.assertFalse(self.reimager.attempt(self._BUILD, self._POOL,
                                               self.devserver,
                                               rjob.record_entry, True,
                                               [], self._DEPENDENCIES))
        self.reimager.clear_reimaged_host_state(self._BUILD)


    def testReimageThatNeverHappened(self):
        """Should attempt a reimage and record that it didn't run."""
        canary = FakeJob()
        statuses = {'hostless': job_status.Status('ABORT', 'big_job_name')}
        self.expect_attempt(canary, statuses)

        rjob = self.mox.CreateMock(base_job.base_job)
        self.mox.ReplayAll()
        self.reimager.attempt(self._BUILD, self._POOL, self.devserver,
                              rjob.record_entry, True, [],
                              self._DEPENDENCIES)
        self.reimager.clear_reimaged_host_state(self._BUILD)


    def testReimageThatRaised(self):
        """Should attempt a reimage that raises an exception and record that."""
        canary = FakeJob()
        ex_message = 'Oh no!'
        statuses = {'hostless': job_status.Status('ABORT', 'fake_job')}
        self.expect_attempt(canary, statuses=statuses, ex=Exception(ex_message))

        rjob = self.mox.CreateMock(base_job.base_job)
        rjob.record_entry(StatusContains.CreateFromStrings('START'))
        rjob.record_entry(StatusContains.CreateFromStrings('ERROR',
                                                           reason=ex_message))
        rjob.record_entry(StatusContains.CreateFromStrings('END ERROR'))
        self.mox.ReplayAll()
        self.reimager.attempt(self._BUILD, self._POOL, self.devserver,
                              rjob.record_entry, True, [], self._DEPENDENCIES)
        self.reimager.clear_reimaged_host_state(self._BUILD)


    def testSuccessfulReimageThatCouldNotScheduleRightAway(self):
        """Should attempt reimage, ignoring host availability; record success.
        """
        canary = FakeJob()
        statuses = {canary.hostnames[0]: job_status.Status('GOOD',
                                                           canary.hostnames[0])}
        self.expect_attempt(canary, statuses, check_hosts=False)

        rjob = self.mox.CreateMock(base_job.base_job)
        self.reimager._clear_build_state(mox.StrContains(canary.hostnames[0]))
        self.mox.ReplayAll()
        self.assertTrue(self.reimager.attempt(self._BUILD, self._POOL,
                                              self.devserver,
                                              rjob.record_entry, False,
                                              [], self._DEPENDENCIES))
        self.reimager.clear_reimaged_host_state(self._BUILD)


    def testReimageThatCouldNotSchedule(self):
        """Should attempt a reimage that can't be scheduled."""
        self.mox.StubOutWithMock(self.reimager, '_ensure_version_label')
        self.mox.StubOutWithMock(self.reimager, '_gather_hosts_from_host_specs')
        self.mox.StubOutWithMock(self.reimager, '_choose_hosts')

        alarm_string = 'alarm!'
        self.reimager._ensure_version_label(mox.StrContains(self._BUILD))
        self.reimager._gather_hosts_from_host_specs(
            mox.IgnoreArg()).AndReturn({})
        self.reimager._choose_hosts(
            mox.IgnoreArg(),
            mox.IgnoreArg(),
            True).AndRaise(error.InadequateHostsException(alarm_string))

        rjob = self.mox.CreateMock(base_job.base_job)
        rjob.record_entry(StatusContains.CreateFromStrings('START'))
        rjob.record_entry(StatusContains.CreateFromStrings('WARN',
                                                           reason=alarm_string))
        rjob.record_entry(StatusContains.CreateFromStrings('END WARN'))
        self.mox.ReplayAll()
        self.reimager.attempt(self._BUILD, self._POOL, self.devserver,
                              rjob.record_entry, True, [], self._DEPENDENCIES)
        self.reimager.clear_reimaged_host_state(self._BUILD)


    def testReimageWithNoAvailableHosts(self):
        """Should attempt a reimage while all hosts are dead."""
        self.mox.StubOutWithMock(self.reimager, '_ensure_version_label')
        self.reimager._ensure_version_label(mox.StrContains(self._BUILD))

        self.mox.StubOutWithMock(self.reimager, '_gather_hosts_from_host_specs')
        self.reimager._gather_hosts_from_host_specs(
            mox.IgnoreArg()).AndReturn({})

        self.mox.StubOutWithMock(self.reimager, '_choose_hosts')
        alarm_string = 'alarm!'
        self.reimager._choose_hosts(
            mox.IgnoreArg(),
            mox.IgnoreArg(),
            True).AndRaise(error.NoHostsException(alarm_string))

        rjob = self.mox.CreateMock(base_job.base_job)
        rjob.record_entry(StatusContains.CreateFromStrings('START'))
        rjob.record_entry(StatusContains.CreateFromStrings('ERROR',
                                                           reason=alarm_string))
        rjob.record_entry(StatusContains.CreateFromStrings('END ERROR'))
        self.mox.ReplayAll()
        self.reimager.attempt(self._BUILD, self._POOL, self.devserver,
                              rjob.record_entry, True, [], self._DEPENDENCIES)
        self.reimager.clear_reimaged_host_state(self._BUILD)
