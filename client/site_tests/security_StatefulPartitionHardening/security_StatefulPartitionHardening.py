# Copyright 2018 The Chromium OS Authors. All rights reserved.
# Use of this source code is governed by a BSD-style license that can be
# found in the LICENSE file.

import logging
import os
import posix
import tempfile

from autotest_lib.client.bin import test
from autotest_lib.client.common_lib import error


class security_StatefulPartitionHardening(test.test):
    """
    Creates symlinks/FIFOs in various locations and attempts to access them,
    checking that observed behavior matches the expected inode security policy
    configured in chromeos_startup.
    """
    version = 1


    _BLOCKED_LOCATIONS = [
            '/mnt/stateful_partition',
            '/var',
    ]

    _ALLOWED_LOCATIONS = [
            '/tmp',
    ]

    _SYMLINK_EXCEPTIONS = [
            '/home',
            '/var/cache/echo',
            '/var/cache/vpd',
            '/var/lib/timezone',
            '/var/log',
    ]


    def __init__(self, *args, **kwargs):
        super(security_StatefulPartitionHardening,
            self).__init__(*args, **kwargs)
        self._links_created = []
        self._dirs_created = []
        self._failure = False


    def cleanup(self):
        """
        Removes symlinks and paths created during test execution after testing.
        """
        for path in reversed(self._links_created):
            os.unlink(path)

        for path in reversed(self._dirs_created):
            os.rmdir(path)

        super(security_StatefulPartitionHardening, self).cleanup()


    def _fail(self, msg):
        """
        Log failure message and record failure.

        @param msg: String to log.

        """
        logging.error(msg)
        self._failure = True


    def _can_open(self, location):
        """
        Attempt to open symlink.

        @param location: Path to the symlink for opening.

        @returns True if the path can be opened, False otherwise.

        """
        try:
            open(location, 'a+').close()
            return True
        except IOError:
            return False


    def _can_open_fifo(self, location):
        """
        Attempt to open FIFO.

        @param location: Path to the FIFO for opening.

        @returns True if the path can be opened, False otherwise.

        """
        try:
            fifo = posix.open(location, posix.O_NONBLOCK)
            posix.close(fifo)
            return True
        except IOError:
            return False


    def _check_open_succeeds(self, location):
        """
        Attempt to open symlink and log if failure.

        @param location: Path to the symlink for opening.

        """
        if not self._can_open(location):
            self._fail('Path access failed unexpectedly on %s' % location)


    def _check_open_fifo_succeeds(self, location):
        """
        Attempt to open symlink and log if failure.

        @param location: Path to the symlink for opening.

        """
        if not self._can_open_fifo(location):
            self._fail('Path access failed unexpectedly on %s' % location)


    def _check_open_fails(self, location):
        """
        Attempt to open path and log if success.

        @param location: Path to the file for opening.

        """
        if self._can_open(location):
            self._fail('Path access succeeded unexpectedly on %s' % location)


    def _assert_realpath(self, path, expected):
        """
        Make sure path matches expected path when symlinks are resolved.

        @param path: Path for which to resolve symlinks.

        @param expected: Expected path.

        @raises TestError if there is an unexpected symlink in the path.

        """
        resolved = os.path.realpath(path)
        if resolved != expected:
            raise error.TestError('Bad canonical path for %s: %s vs %s' %
                                  (path, resolved, expected))


    def _mkdir(self, location):
        """
        Make directory at location.

        @param location: Path to directory to be created.

        """
        dir_name = tempfile.mktemp('', 'security_RootfsStatefulHardening-',
                                   location)
        os.mkdir(dir_name)
        self._dirs_created.append(dir_name)
        return dir_name


    def _symlink(self, location, target):
        """
        Create symlink from location dir to target and add it to symlink list.

        @param location: Dir in which to create temporary symlink file.

        @param target: Target of the symlink.

        @returns the name of the temporary symlink file.

        """
        link_name = tempfile.mktemp('', 'security_RootfsStatefulHardening-',
                                    location)
        os.symlink(target, link_name)
        self._links_created.append(link_name)
        return link_name


    def _fifo(self, location):
        """
        Create FIFO in location dir and add it to FIFO list.

        @param location: Dir in which to create temporary FIFO.

        @returns the name of the temporary FIFO.

        """
        fifo_name = tempfile.mktemp('', 'security_RootfsStatefulHardening-',
                                    location)
        os.mkfifo(fifo_name)
        self._links_created.append(fifo_name)
        return fifo_name


    def _test_blocked_traversal(self, path, canonical):
        """
        Test that symlink traversal is blocked for given path.

        @param path: Path to symlink. Access should fail.

        @param canonical: Path to target. Access should succeed.

        """
        self._assert_realpath(path, canonical)
        self._check_open_succeeds(canonical)
        self._check_open_fails(path)


    def _test_blocked_traversal_simple(self, location):
        """
        Test that symlink traversal is blocked in the simplest case.

        @param location: Path to the symlink file.

        """
        name = self._symlink(location, '/dev/null')
        self._test_blocked_traversal(name, '/dev/null')


    def _test_blocked_traversal_parent(self, location):
        """
        Test that traversal is blocked when symlink is in path.

        @param location: Path to the symlink to be traversed.

        """
        name = self._symlink(location, '/dev')
        self._test_blocked_traversal(os.path.join(name, 'null'), '/dev/null')


    def _test_allowed_traversal(self, location):
        """
        Test that symlink traversal is allowed.

        @param location: Path to the symlink to be traversed.

        """
        name = self._symlink(location, '/dev/null')
        self._check_open_succeeds(name)


    def _test_blocked_fifo(self, location):
        """
        Test that FIFO access is blocked.

        @param location: Path to the FIFO to attempt to open.

        """
        fifo = self._fifo(location)
        self._check_open_fails(fifo)


    def _test_allowed_fifo(self, location):
        """
        Test that FIFO access is allowed.

        @param location: Path to the FIFO to attempt to open.

        """
        fifo = self._fifo(location)
        self._check_open_fifo_succeeds(fifo)


    def _test_symlink_traversal(self, location, access_allowed):
        """
        Test symlink traversal for given location.

        @param location: Path to the symlink to be traversed.

        @param access_allowed: Boolean regarding expected success of traversal.

        """
        if access_allowed:
            self._test_allowed_traversal(location)
            self._test_allowed_traversal(self._mkdir(location))
        else:
            self._test_blocked_traversal_simple(location)
            self._test_blocked_traversal_simple(self._mkdir(location))
            self._test_blocked_traversal_parent(location)


    def _test_fifo_open(self, location, access_allowed):
        """
        Test FIFO opening for given location.

        @param location: Path to the FIFO to be opened.

        @param access_allowed: Boolean regarding expected success of FIFO open.

        """
        if access_allowed:
            self._test_allowed_fifo(location)
            self._test_allowed_fifo(self._mkdir(location))
        else:
            self._test_blocked_fifo(location)
            self._test_blocked_fifo(self._mkdir(location))


    def run_once(self):
        """
        Runs the test, creating symlinks/FIFOs and checking access behavior.
        """
        # Test blocked access in blocked locations and their subdirs.
        for location in self._BLOCKED_LOCATIONS:
            self._test_symlink_traversal(location, False)
            self._test_fifo_open(location, False)

        # Test access allowed in allowed locations.
        for location in self._ALLOWED_LOCATIONS:
            self._test_symlink_traversal(location, True)
            self._test_fifo_open(location, True)

        # Test symlink traversal allowed in exempted locations and their
        # subdirs.
        for location in self._SYMLINK_EXCEPTIONS:
            self._test_symlink_traversal(location, True)

        # Test a more complicated case where the blocked symlink isn't
        # actually present as a component in the accessed path, but gets
        # introduced indirectly by an allowed symlink.
        blocked = self._symlink(self._BLOCKED_LOCATIONS[0], '/dev/null')
        allowed = self._symlink(self._SYMLINK_EXCEPTIONS[0], blocked)
        self._test_blocked_traversal(allowed, '/dev/null')

        # Make the test fail if any unexpected behaviour got detected. Note that
        # the error log output that will be included in the failure message
        # mentions the failed location to aid debugging.
        if self._failure:
            raise error.TestFail('Unexpected symlink/FIFO access behavior')
