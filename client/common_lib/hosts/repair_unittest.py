# Copyright 2016 The Chromium OS Authors. All rights reserved.
# Use of this source code is governed by a BSD-style license that can be
# found in the LICENSE file.

"""Unit tests for the `repair` module."""

import functools
import logging
import unittest

import common
from autotest_lib.client.common_lib import hosts


class _StubHost(object):
    """
    Stub class to fill in the relevant methods of `Host`.

    This class provides mocking and stub behaviors for `Host` for use by
    tests within this module.  The class implements only those methods
    that `Verifier` and `RepairAction` actually use.
    """

    def __init__(self):
        self._record_sequence = []


    def record(self, status_code, subdir, operation, status=''):
        """
        Mock method to capture records written to `status.log`.

        Each record is remembered in order to be checked for correctness
        by individual tests later.

        @param status_code  As for `Host.record()`.
        @param subdir       As for `Host.record()`.
        @param operation    As for `Host.record()`.
        @param status       As for `Host.record()`.
        """
        full_record = (status_code, subdir, operation, status)
        self._record_sequence.append(full_record)


    def get_log_records(self):
        """
        Return the records logged for this fake host.

        The returned list of records excludes records where the
        `operation` parameter is not in `tagset`.

        @param tagset   Only include log records with these tags.
        """
        return self._record_sequence


class _StubVerifier(hosts.Verifier):
    """
    Stub implementation of `Verifier` for testing purposes.

    This is a full implementation of a concrete `Verifier` subclass
    designed to allow calling unit tests control over whether it passes
    or fails.
    """

    def __init__(self, tag, deps, fail_count):
        super(_StubVerifier, self).__init__(tag, deps)
        self.verify_count = 0
        self._fail_count = fail_count
        self._description = 'Testing verify() for "%s"' % tag
        self.message = 'Failing "%s" by request' % tag


    def __repr__(self):
        return '_StubVerifier(%r, %r, %r)' % (
                self.tag, self._dependency_list, self._fail_count)


    def verify(self, host):
        self.verify_count += 1
        if self._fail_count:
            raise hosts.AutotestHostVerifyError(self.message)


    def try_repair(self):
        """Bring ourselves one step closer to working."""
        if self._fail_count:
            self._fail_count -= 1


    def get_log_record(self, success):
        """
        Return a host log record for this verifier.

        Calculates the arguments expected to be passed to
        `Host.record()` by `Verifier._verify_host()` when this verifier
        runs.  If `success` is true, the returned record will be for
        a successful verification.  Otherwise, the returned record will
        be for a failure.

        @param success  If true, return a success record.  Otherwise,
                        return a failure record.
        """
        if success:
            return ('GOOD', None, self._verify_tag, '')
        else:
            return ('FAIL', None, self._verify_tag, self.message)


    @property
    def description(self):
        return self._description


class _VerifierTestCases(unittest.TestCase):
    """
    Abstract base class for all Repair and Verify test cases.

    This class provides a `_make_verifier()` method to create
    `_StubVerifier` instances for test cases.  Constructed verifiers
    are remembered in `self.verifiers`, a dictionary indexed by the tag
    used to construct the verifier.
    """

    def setUp(self):
        logging.disable(logging.CRITICAL)
        self._fake_host = _StubHost()
        self.verifiers = {}


    def tearDown(self):
        logging.disable(logging.NOTSET)


    def _make_verifier(self, count, tag, deps):
        """
        Make a `_StubVerifier`, and remember it.

        Constructs a `_StubVerifier` from the given arguments,
        and remember it in `self.verifiers`.

        @param count  As for the `_StubVerifer` constructor.
        @param tag    As for the `_StubVerifer` constructor.
        @param deps   As for the `_StubVerifer` constructor.
        """
        verifier = _StubVerifier(tag, deps, count)
        self.verifiers[tag] = verifier
        return verifier


    def _check_log_records(self, *record_data):
        """
        Assert that log records occurred as expected.

        Elements of `record_data` should be tuples of the form
        `(tag, success)`, describing one expected log record.
        The verifier provides the expected log record based on the
        success flag.

        The actually logged records are extracted from
        `self._fake_host`.  Only log records from verifiers in
        `self.verifiers` are considered.  Other log records (i.e. the
        special null verifiers in `RepairStrategy`) are ignored.

        @param record_data  List describing the expected record events.
        """
        expected_records = []
        for tag, success in record_data:
            expected_records.append(
                    self.verifiers[tag].get_log_record(success))
        actual_records = self._fake_host.get_log_records()
        self.assertEqual(expected_records, actual_records)


class VerifyTests(_VerifierTestCases):
    """
    Unit tests for `Verifier`.

    The tests in this class test the fundamental behaviors of
    the `Verifier` class:
      * Results from the `verify()` method are cached; the method is
        only called the first time that `_verify_host()` is called.
      * The `_verify_host()` method uses `Host.record()` to log the
        outcome of every call to the `verify()` method.
      * When a dependency fails, the dependent verifier isn't called.
      * Verifier calls are made in the order required by the DAG.

    The test cases don't use `RepairStrategy` to build DAG structures,
    but instead rely on custom-built DAGs.
    """

    def test_success(self):
        """
        Test proper handling of a successful verification.

        Construct and call a simple, single-node verification that will
        pass.  Assert the following:
          * The `verify()` method is called once.
          * The expected 'GOOD' record is logged via `Host.record()`.
          * If `_verify_host()` is called more than once, there are no
            visible side-effects after the first call.
        """
        verifier = self._make_verifier(0, 'pass', [])
        for i in range(0, 2):
            verifier._verify_host(self._fake_host)
            self.assertEqual(verifier.verify_count, 1)
            self._check_log_records(('pass', True))


    def test_fail(self):
        """
        Test proper handling of verification failure.

        Construct and call a simple, single-node verification that will
        fail.  Assert the following:
          * The failure is reported with the actual exception raised
            by the verifier.
          * The `verify()` method is called once.
          * The expected 'FAIL' record is logged via `Host.record()`.
          * If `_verify_host()` is called more than once, there are no
            visible side-effects after the first call.
        """
        verifier = self._make_verifier(1, 'fail', [])
        for i in range(0, 2):
            with self.assertRaises(hosts.AutotestHostVerifyError) as e:
                verifier._verify_host(self._fake_host)
            self.assertEqual(verifier.verify_count, 1)
            self.assertEqual(verifier.message, str(e.exception))
            self._check_log_records(('fail', False))


    def test_dependency_success(self):
        """
        Test proper handling of dependencies that succeed.

        Construct and call a two-node verification with one node
        dependent on the other, where both nodes will pass.  Assert the
        following:
          * The `verify()` method for both nodes is called once.
          * The expected 'GOOD' record is logged via `Host.record()`
            for both nodes.
          * If `_verify_host()` is called more than once, there are no
            visible side-effects after the first call.
        """
        child = self._make_verifier(0, 'pass', [])
        parent = self._make_verifier(0, 'parent', [child])
        for i in range(0, 2):
            parent._verify_host(self._fake_host)
            self.assertEqual(parent.verify_count, 1)
            self.assertEqual(child.verify_count, 1)
            self._check_log_records(('pass', True),
                                    ('parent', True))


    def test_dependency_fail(self):
        """
        Test proper handling of dependencies that fail.

        Construct and call a two-node verification with one node
        dependent on the other, where the dependency will fail.  Assert
        the following:
          * The verification exception is `AutotestVerifyDependencyError`,
            and the exception argument is the description of the failed
            node.
          * The `verify()` method for the failing node is called once,
            and for the other node, not at all.
          * The expected 'FAIL' record is logged via `Host.record()`
            for the single failed node.
          * If `_verify_host()` is called more than once, there are no
            visible side-effects after the first call.
        """
        child = self._make_verifier(1, 'fail', [])
        parent = self._make_verifier(0, 'parent', [child])
        for i in range(0, 2):
            with self.assertRaises(hosts.AutotestVerifyDependencyError) as e:
                parent._verify_host(self._fake_host)
            self.assertEqual(e.exception.args, (child.description,))
            self.assertEqual(child.verify_count, 1)
            self.assertEqual(parent.verify_count, 0)
            self._check_log_records(('fail', False))


    def test_two_dependencies_pass(self):
        """
        Test proper handling with two passing dependencies.

        Construct and call a three-node verification with one node
        dependent on the other two, where all nodes will pass.  Assert
        the following:
          * The `verify()` method for all nodes is called once.
          * The expected 'GOOD' records are logged via `Host.record()`
            for all three nodes.
          * If `_verify_host()` is called more than once, there are no
            visible side-effects after the first call.
        """
        left = self._make_verifier(0, 'left', [])
        right = self._make_verifier(0, 'right', [])
        top = self._make_verifier(0, 'top', [left, right])
        for i in range(0, 2):
            top._verify_host(self._fake_host)
            self.assertEqual(top.verify_count, 1)
            self.assertEqual(left.verify_count, 1)
            self.assertEqual(right.verify_count, 1)
            self._check_log_records(('left', True),
                                    ('right', True),
                                    ('top', True))


    def test_two_dependencies_fail(self):
        """
        Test proper handling with two failing dependencies.

        Construct and call a three-node verification with one node
        dependent on the other two, where both dependencies will fail.
        Assert the following:
          * The verification exception is `AutotestVerifyDependencyError`,
            and the exception argument has the descriptions of both the
            failed nodes.
          * The `verify()` method for each failing node is called once,
            and for the parent node not at all.
          * The expected 'FAIL' records are logged via `Host.record()`
            for the failing nodes.
          * If `_verify_host()` is called more than once, there are no
            visible side-effects after the first call.
        """
        left = self._make_verifier(1, 'left', [])
        right = self._make_verifier(1, 'right', [])
        top = self._make_verifier(0, 'top', [left, right])
        for i in range(0, 2):
            with self.assertRaises(hosts.AutotestVerifyDependencyError) as e:
                top._verify_host(self._fake_host)
            self.assertEqual(sorted(e.exception.args),
                             sorted((left.description,
                                     right.description)))
            self.assertEqual(top.verify_count, 0)
            self.assertEqual(left.verify_count, 1)
            self.assertEqual(right.verify_count, 1)
            self._check_log_records(('left', False),
                                    ('right', False))


    def test_two_dependencies_mixed(self):
        """
        Test proper handling with mixed dependencies.

        Construct and call a three-node verification with one node
        dependent on the other two, where one dependency will pass,
        and one will fail.  Assert the following:
          * The verification exception is `AutotestVerifyDependencyError`,
            and the exception argument has the descriptions of the
            single failed node.
          * The `verify()` method for each dependency is called once,
            and for the parent node not at all.
          * The expected 'GOOD' and 'FAIL' records are logged via
            `Host.record()` for the dependencies.
          * If `_verify_host()` is called more than once, there are no
            visible side-effects after the first call.
        """
        left = self._make_verifier(1, 'left', [])
        right = self._make_verifier(0, 'right', [])
        top = self._make_verifier(0, 'top', [left, right])
        for i in range(0, 2):
            with self.assertRaises(hosts.AutotestVerifyDependencyError) as e:
                top._verify_host(self._fake_host)
            self.assertEqual(e.exception.args, (left.description,))
            self.assertEqual(top.verify_count, 0)
            self.assertEqual(left.verify_count, 1)
            self.assertEqual(right.verify_count, 1)
            self._check_log_records(('left', False),
                                    ('right', True))


    def test_diamond_pass(self):
        """
        Test a "diamond" structure DAG with all nodes passing.

        Construct and call a "diamond" structure DAG where all nodes
        will pass:

                TOP
               /   \
            LEFT   RIGHT
               \   /
               BOTTOM

       Assert the following:
          * The `verify()` method for all nodes is called once.
          * The expected 'GOOD' records are logged via `Host.record()`
            for all nodes.
          * If `_verify_host()` is called more than once, there are no
            visible side-effects after the first call.
        """
        bottom = self._make_verifier(0, 'bottom', [])
        left = self._make_verifier(0, 'left', [bottom])
        right = self._make_verifier(0, 'right', [bottom])
        top = self._make_verifier(0, 'top', [left, right])
        for i in range(0, 2):
            top._verify_host(self._fake_host)
            self.assertEqual(top.verify_count, 1)
            self.assertEqual(left.verify_count, 1)
            self.assertEqual(right.verify_count, 1)
            self.assertEqual(bottom.verify_count, 1)
            self._check_log_records(('bottom', True),
                                    ('left', True),
                                    ('right', True),
                                    ('top', True))


    def test_diamond_fail(self):
        """
        Test a "diamond" structure DAG with the bottom node failing.

        Construct and call a "diamond" structure DAG where the bottom
        node will fail:

                TOP
               /   \
            LEFT   RIGHT
               \   /
               BOTTOM

        Assert the following:
          * The verification exception is `AutotestVerifyDependencyError`,
            and the exception argument has the description of the
            "bottom" node.
          * The `verify()` method for the "bottom" node is called once,
            and for the other nodes not at all.
          * The expected 'FAIL' record is logged via `Host.record()`
            for the "bottom" node.
          * If `_verify_host()` is called more than once, there are no
            visible side-effects after the first call.
        """
        bottom = self._make_verifier(1, 'bottom', [])
        left = self._make_verifier(0, 'left', [bottom])
        right = self._make_verifier(0, 'right', [bottom])
        top = self._make_verifier(0, 'top', [left, right])
        for i in range(0, 2):
            with self.assertRaises(hosts.AutotestVerifyDependencyError) as e:
                top._verify_host(self._fake_host)
            self.assertEqual(e.exception.args, (bottom.description,))
            self.assertEqual(top.verify_count, 0)
            self.assertEqual(left.verify_count, 0)
            self.assertEqual(right.verify_count, 0)
            self.assertEqual(bottom.verify_count, 1)
            self._check_log_records(('bottom', False))


class RepairStrategyTests(_VerifierTestCases):
    """
    Unit tests for `RepairStrategy`.

    These unit tests focus on verifying that the `RepairStrategy`
    constructor creates the expected DAG structure.  Functional testing
    here is confined to asserting that `RepairStrategy.verify()`
    properly distinguishes success from failure.  Testing the behavior
    of specific DAG structures is left to tests in `VerifyTests`.
    """

    def _make_verify_data(self, *input_data):
        """
        Create `verify_data` for the `RepairStrategy` constructor.

        `RepairStrategy` expects `verify_data` as a list of tuples
        of the form `(constructor, tag, deps)`.  Each item in
        `input_data` is a tuple of the form `(tag, count, deps)` that
        creates one entry in the returned list of `verify_data` tuples
        as follows:
          * `count` is used to create a constructor function that calls
            `self._make_verifier()` with that value plus plus the
            arguments provided by the `RepairStrategy` constructor.
          * `tag` and `deps` will be passed as-is to the `RepairStrategy`
            constructor.

        @param input_data   A list of tuples, each representing one
                            tuple in the `verify_data` list.
        @return   A list suitable to be the `verify_data` parameter for
                  the `RepairStrategy` constructor.
        """
        strategy_data = []
        for tag, count, deps in input_data:
            construct = functools.partial(self._make_verifier, count)
            strategy_data.append((construct, tag, deps))
        return strategy_data


    def test_single_node(self):
        """
        Test construction of a single-node verification DAG.

        Assert that the structure looks like this:

            Root Node -> Main Node
        """
        verify_data = self._make_verify_data(('main', 0, ()))
        strategy = hosts.RepairStrategy(verify_data)
        verifier = self.verifiers['main']
        self.assertEqual(
                strategy._verify_root._dependency_list,
                [verifier])
        self.assertEqual(verifier._dependency_list, [])


    def test_single_dependency(self):
        """
        Test construction of a two-node dependency chain.

        Assert that the structure looks like this:

            Root Node -> Parent Node -> Child Node
        """
        verify_data = self._make_verify_data(
                ('child', 0, ()),
                ('parent', 0, ('child',)))
        strategy = hosts.RepairStrategy(verify_data)
        parent = self.verifiers['parent']
        child = self.verifiers['child']
        self.assertEqual(
                strategy._verify_root._dependency_list, [parent])
        self.assertEqual(
                parent._dependency_list, [child])
        self.assertEqual(
                child._dependency_list, [])


    def test_two_nodes_and_dependency(self):
        """
        Test construction of two nodes with a shared dependency.

        Assert that the structure looks like this:

            Root Node -> Left Node ---\
                      \                -> Bottom Node
                        -> Right Node /
        """
        verify_data = self._make_verify_data(
                ('bottom', 0, ()),
                ('left', 0, ('bottom',)),
                ('right', 0, ('bottom',)))
        strategy = hosts.RepairStrategy(verify_data)
        bottom = self.verifiers['bottom']
        left = self.verifiers['left']
        right = self.verifiers['right']
        self.assertEqual(
                strategy._verify_root._dependency_list,
                [left, right])
        self.assertEqual(left._dependency_list, [bottom])
        self.assertEqual(right._dependency_list, [bottom])
        self.assertEqual(bottom._dependency_list, [])


    def test_three_nodes(self):
        """
        Test construction of three nodes with no dependencies.

        Assert that the structure looks like this:

                       -> Node One
                      /
            Root Node -> Node Two
                      \
                       -> Node Three

        N.B.  This test exists to enforce ordering expectations of
        root-level DAG nodes.  Three nodes are used to make it unlikely
        that randomly ordered roots will match expectations.
        """
        verify_data = self._make_verify_data(
                ('one', 0, ()),
                ('two', 0, ()),
                ('three', 0, ()))
        strategy = hosts.RepairStrategy(verify_data)
        one = self.verifiers['one']
        two = self.verifiers['two']
        three = self.verifiers['three']
        self.assertEqual(
                strategy._verify_root._dependency_list,
                [one, two, three])
        self.assertEqual(one._dependency_list, [])
        self.assertEqual(two._dependency_list, [])
        self.assertEqual(three._dependency_list, [])


    def test_verify_passes(self):
        """
        Test with a single passing verifier.

        Build a `RepairStrategy` with a single verifier that will
        pass when called.  Assert that the strategy's `verify()`
        method passes without rasing an exception.
        """
        verify_data = self._make_verify_data(('pass', 0, ()))
        strategy = hosts.RepairStrategy(verify_data)
        strategy.verify(self._fake_host)


    def test_verify_fails(self):
        """
        Test with a single failing verifier.

        Build a `RepairStrategy` with a single verifier that will
        fail when called.  Assert that the strategy's `verify()`
        method fails by raising an exception.
        """
        verify_data = self._make_verify_data(('fail', 1, ()))
        strategy = hosts.RepairStrategy(verify_data)
        with self.assertRaises(Exception) as e:
            strategy.verify(self._fake_host)


if __name__ == '__main__':
    unittest.main()
