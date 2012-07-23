#!/usr/bin/python
#
# Copyright (c) 2012 The Chromium OS Authors. All rights reserved.
# Use of this source code is governed by a BSD-style license that can be
# found in the LICENSE file.

"""Unit tests for server/cros/dynamic_suite/host_spec.py."""

import mox
import unittest

from autotest_lib.server.cros.dynamic_suite import host_spec
from autotest_lib.server.cros.dynamic_suite.fakes import FakeHost


class HostSpecTest(mox.MoxTestBase):
    """Unit tests for dynamic_suite.host_spec module.

    @var _BOARD: fake board to reimage
    """


    _BOARD = 'board'


    def testOrderSpecsByComplexity(self):
        """Should return new host spec list with simpler entries later."""
        specs = [host_spec.HostSpec([self._BOARD]),
                 host_spec.HostSpec([self._BOARD, 'pool:bvt']),
                 host_spec.HostSpec([self._BOARD, 'label1'])]
        reordered = host_spec.order_by_complexity(specs)

        for spec in specs[1:]:
            self.assertTrue(spec in reordered[:-1])
        self.assertEquals(specs[0], reordered[-1])


class HostGroupTest(mox.MoxTestBase):
    """Unit tests for dynamic_suite.host_spec.HostGroup derived classes.
    """


    def testCanConstructExplicit(self):
        """Should be able to make an ExplicitHostGroup."""
        host_list = [FakeHost('h1'), FakeHost('h2'), FakeHost('h3')]
        hosts_per_spec = {host_spec.HostSpec(['l1']): host_list[:1],
                          host_spec.HostSpec(['l2']): host_list[1:]}
        group = host_spec.ExplicitHostGroup(hosts_per_spec)
        self.assertEquals(sorted([h.hostname for h in host_list]),
                          sorted(group.as_args()['hosts']))


    def testExplicitEnforcesHostUniqueness(self):
        """Should fail to make ExplicitHostGroup with duplicate hosts."""
        host_list = [FakeHost('h1'), FakeHost('h2'), FakeHost('h3')]
        hosts_per_spec = {host_spec.HostSpec(['l1']): host_list[:1],
                          host_spec.HostSpec(['l2']): host_list}
        self.assertRaises(ValueError,
                          host_spec.ExplicitHostGroup, hosts_per_spec)


    def testCanConstructByMetahostsWithDependencies(self):
        """Should be able to make a HostGroup from labels."""
        labels = ['meta_host', 'dep1', 'dep2']
        num = 3
        group = host_spec.MetaHostGroup(labels, num)
        args = group.as_args()
        self.assertEquals(labels[:1] * num, args['meta_hosts'])
        self.assertEquals(labels[1:], args['dependencies'])


    def testCanTrackSuccessExplicit(self):
        """Track success/failure in an ExplicitHostGroup."""
        host_list = [FakeHost('h1'), FakeHost('h2'), FakeHost('h3')]
        specs = [host_spec.HostSpec(['l1']), host_spec.HostSpec(['l2'])]
        hosts_per_spec = {specs[0]: host_list[:1], specs[1]: host_list[1:]}
        group = host_spec.ExplicitHostGroup(hosts_per_spec)

        # Reimage just the one host that satisfies specs[0].
        group.mark_host_success(host_list[0].hostname)
        self.assertTrue(group.enough_hosts_succeeded())
        self.assertTrue(specs[1] in group.doomed_specs)

        # Reimage some host that satisfies specs[1].
        group.mark_host_success(host_list[2].hostname)
        self.assertTrue(group.enough_hosts_succeeded())
        self.assertFalse(group.doomed_specs)


    def testExplicitCanTrackUnsatisfiedSpecs(self):
        """Track unsatisfiable HostSpecs in ExplicitHostGroup."""
        group = host_spec.ExplicitHostGroup()
        unsatisfiable_spec = host_spec.HostSpec(['l1'])
        group.add_host_for_spec(unsatisfiable_spec, None)
        self.assertTrue(unsatisfiable_spec in group.unsatisfied_specs)


    def testExplicitOneHostEnoughToSatisfySpecs(self):
        """One host is enough to satisfy a HostSpec in ExplicitHostGroup."""
        satisfiable_spec = host_spec.HostSpec(['l1'])
        group = host_spec.ExplicitHostGroup()
        group.add_host_for_spec(satisfiable_spec, FakeHost('h1'))
        group.add_host_for_spec(satisfiable_spec, None)
        self.assertTrue(satisfiable_spec not in group.unsatisfied_specs)

        group = host_spec.ExplicitHostGroup()
        group.add_host_for_spec(satisfiable_spec, None)
        group.add_host_for_spec(satisfiable_spec, FakeHost('h1'))
        self.assertTrue(satisfiable_spec not in group.unsatisfied_specs)


    def testCanTrackSuccessMeta(self):
        """Track success/failure in a MetaHostGroup."""
        labels = ['meta_host', 'dep1', 'dep2']
        num = 3
        group = host_spec.MetaHostGroup(labels, num)

        self.assertFalse(group.enough_hosts_succeeded())

        group.mark_host_success('h1')
        self.assertTrue(group.enough_hosts_succeeded())
