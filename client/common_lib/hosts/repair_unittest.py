# Copyright 2016 The Chromium OS Authors. All rights reserved.
# Use of this source code is governed by a BSD-style license that can be
# found in the LICENSE file.

"""Unit tests for the `repair` module."""

import unittest
import logging

import common
from autotest_lib.client.common_lib import hosts


class _StubHost(object):
    """Stub class to fill in the relevant methods of `Host`.

    This class provides mocking and stub behaviors for `Host` for use by
    tests within this module.  The class implements only methods that
    `Verifier` and `RepairAction` actually use.
    """

    def __init__(self):
        self.log_records = {}


    def record(self, status_code, subdir, operation, status=''):
        """Mock method to capture records written to `status.log`.

        Each record is remembered in order to be checked for correctness
        by individual tests later.

        @param status_code As for `Host.record()`.
        @param subdir As for `Host.record()`.
        @param operation As for `Host.record()`.
        @param status As for `Host.record()`.
        """
        log_record = (status_code, subdir, status)
        self.log_records.setdefault(operation, []).append(log_record)


class _StubVerifier(hosts.Verifier):
    """Stub implementation of `Verifier` for testing purposes.

    A full implementation of a concrete `Verifier` subclass designed to
    allow calling unit tests control over whether it passes or fails.
    """

    def __init__(self, deps, repair_count, tag):
        self.verify_count = 0
        self._repair_count = repair_count
        self._tag = tag
        self._description = 'Testing verify() for "%s"' % tag
        self.message = 'Failing "%s" by request' % tag
        super(_StubVerifier, self).__init__(deps)


    def verify(self, host):
        self.verify_count += 1
        if self._repair_count:
            raise hosts.AutotestHostVerifyError(self.message)


    def try_repair(self):
        """Bring ourselves one step closer to working."""
        if self._repair_count:
            self._repair_count -= 1


    @property
    def tag(self):
        return self._tag


    @property
    def description(self):
        return self._description


class _VerifierTestCases(unittest.TestCase):
    def setUp(self):
        logging.disable(logging.CRITICAL)


    def tearDown(self):
        logging.disable(logging.NOTSET)


class VerifyTests(_VerifierTestCases):
    """Unit tests for `Verifier`."""

    def test_verify_success(self):
        """Test proper handling of a successful verification.

        Construct and call a simple, single-node verification that will
        pass.  Assert the following:
          * The `verify()` method is called once.
          * The expected 'GOOD' record is logged via `host.record()`.
          * If `_verify_host()` is called more than once, there are no
            visible side-effects after the first call.
        """
        verifier = _StubVerifier([], 0, 'pass')
        fake_host = _StubHost()
        for i in range(0, 2):
            verifier._verify_host(fake_host)
            self.assertEqual(verifier.verify_count, 1)
            key = verifier._verify_tag
            self.assertEqual(fake_host.log_records.get(key),
                             [('GOOD', None, '')])


    def test_verify_fail(self):
        """Test proper handling of verification failure.

        Construct and call a simple, single-node verification that will
        fail.  Assert the following:
          * The failure is reported with the actual exception raised
            by the verifier.
          * The `verify()` method is called once.
          * The expected 'FAIL' record is logged via `host.record()`.
          * If `_verify_host()` is called more than once, there are no
            visible side-effects after the first call.
        """
        verifier = _StubVerifier([], 1, 'fail')
        message = verifier.message
        fake_host = _StubHost()
        for i in range(0, 2):
            with self.assertRaises(hosts.AutotestHostVerifyError) as e:
                verifier._verify_host(fake_host)
            self.assertEqual(verifier.verify_count, 1)
            self.assertEqual(verifier.message, str(e.exception))
            key = verifier._verify_tag
            self.assertEqual(fake_host.log_records.get(key),
                             [('FAIL', None, verifier.message)])


    def test_verify_dependency_success(self):
        """Test proper handling of dependencies that succeed.

        Construct and call a two-node verification with one node
        dependent on the other, where both nodes will pass.  Assert the
        following:
          * The `verify()` method for both nodes is called once.
          * The expected 'GOOD' record is logged via `host.record()`
            for both nodes.
          * If `_verify_host()` is called more than once, there are no
            visible side-effects after the first call.
        """
        child_verifier = _StubVerifier([], 0, 'pass')
        parent_verifier = _StubVerifier([child_verifier], 0, 'parent')
        fake_host = _StubHost()
        for i in range(0, 2):
            parent_verifier._verify_host(fake_host)
            self.assertEqual(parent_verifier.verify_count, 1)
            self.assertEqual(child_verifier.verify_count, 1)
            key = child_verifier._verify_tag
            self.assertEqual(fake_host.log_records.get(key),
                             [('GOOD', None, '')])
            key = parent_verifier._verify_tag
            self.assertEqual(fake_host.log_records.get(key),
                             [('GOOD', None, '')])


    def test_verify_dependency_fail(self):
        """Test proper handling of dependencies that fail.

        Construct and call a two-node verification with one node
        dependent on the other, where the dependency will fail.  Assert
        the following:
          * The verification exception is `AutotestVerifyDependencyError`,
            and the exception argument is the description of the failed
            node.
          * The `verify()` method for the failing node is called once,
            and for the other not, not at all.
          * The expected 'FAIL' record is logged via `host.record()`
            for the single failed node.
          * If `_verify_host()` is called more than once, there are no
            visible side-effects after the first call.
        """
        child_verifier = _StubVerifier([], 1, 'fail')
        parent_verifier = _StubVerifier([child_verifier], 0, 'parent')
        fake_host = _StubHost()
        for i in range(0, 2):
            with self.assertRaises(hosts.AutotestVerifyDependencyError) as e:
                parent_verifier._verify_host(fake_host)
            self.assertEqual(list(e.exception.args),
                             [child_verifier.description])
            self.assertEqual(child_verifier.verify_count, 1)
            self.assertEqual(parent_verifier.verify_count, 0)
            key = child_verifier._verify_tag
            self.assertEqual(fake_host.log_records.get(key),
                             [('FAIL', None, child_verifier.message)])


if __name__ == '__main__':
    unittest.main()
