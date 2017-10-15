# Copyright 2017 The Chromium Authors. All rights reserved.
# Use of this source code is governed by a BSD-style license that can be
# found in the LICENSE file.

from __future__ import absolute_import
from __future__ import division
from __future__ import print_function

import contextlib
import logging
import os
import socket
import sys

import mock
import pytest
import subprocess32

from lucifer import leasing

logger = logging.getLogger(__name__)

# 9999-01-01T00:00:00+00:00
_THE_END = 253370764800


@pytest.mark.slow
def test_get_expired_leases(tmpdir, end_time):
    """Test get_expired_leases()."""
    _make_lease(tmpdir, 123)
    with _make_locked_lease(tmpdir, 124):
        got = list(leasing.get_expired_leases(str(tmpdir)))

    assert all(isinstance(job, leasing.Lease) for job in got)
    # Locked lease should not be returned
    assert [job.id for job in got] == [123]


def test_unlocked_fresh_leases_are_not_expired(tmpdir):
    """Test get_expired_leases()."""
    path = _make_lease(tmpdir, 123)
    os.utime(path, (_THE_END, _THE_END))
    got = list(leasing.get_expired_leases(str(tmpdir)))
    assert len(got) == 0


def test_get_expired_leases_with_sock_files(tmpdir, end_time):
    """Test get_expired_leases()."""
    _make_lease(tmpdir, 123)
    tmpdir.join('124.sock').write('')
    got = list(leasing.get_expired_leases(str(tmpdir)))

    assert all(isinstance(job, leasing.Lease) for job in got)
    # Abort socket should be ignored
    assert [job.id for job in got] == [123]


def test_get_timed_out_leases(tmpdir):
    """Test get_timed_out_leases()."""
    mock_model = mock.Mock()
    (
            mock_model.objects
            .filter()
            .extra()
            .distinct
    ).return_value = [_StubJob(122), _StubJob(123)]
    _make_lease(tmpdir, 123)
    _make_lease(tmpdir, 124)
    got = list(leasing.get_timed_out_leases(mock_model, str(tmpdir)))

    assert all(isinstance(job, leasing.Lease) for job in got)
    assert 123 in [job.id for job in got]
    assert 124 not in [job.id for job in got]


def test_get_marked_aborting_leases(tmpdir):
    """Test get_marked_aborting_leases()."""
    mock_model = mock.Mock()
    (
            mock_model.objects
            .filter()
            .filter()
            .distinct
    ).return_value = [_StubJob(122), _StubJob(123)]
    _make_lease(tmpdir, 123)
    _make_lease(tmpdir, 124)
    got = list(leasing.get_marked_aborting_leases(mock_model, str(tmpdir)))

    assert all(isinstance(job, leasing.Lease) for job in got)
    assert 123 in [job.id for job in got]
    assert 124 not in [job.id for job in got]


def test_Job_cleanup(tmpdir):
    """Test Job.cleanup()."""
    lease_path = _make_lease(tmpdir, 123)
    tmpdir.join('123.sock').write('')
    sock_path = str(tmpdir.join('123.sock'))
    for job in leasing.leases_iter(str(tmpdir)):
        logger.debug('Cleaning up %r', job)
        job.cleanup()
    assert not os.path.exists(lease_path)
    assert not os.path.exists(sock_path)


def test_Job_cleanup_does_not_raise_on_error(tmpdir):
    """Test Job.cleanup()."""
    lease_path = _make_lease(tmpdir, 123)
    tmpdir.join('123.sock').write('')
    sock_path = str(tmpdir.join('123.sock'))
    for job in leasing.leases_iter(str(tmpdir)):
        os.unlink(lease_path)
        os.unlink(sock_path)
        job.cleanup()


@pytest.mark.slow
def test_Job_abort(tmpdir):
    """Test Job.abort()."""
    _make_lease(tmpdir, 123)
    with _abort_socket(tmpdir, 123) as proc:
        expired = list(leasing.leases_iter(str(tmpdir)))
        assert len(expired) > 0
        for job in expired:
            job.abort()
        proc.wait()
        assert proc.returncode == 0


@pytest.mark.slow
def test_Job_abort_with_closed_socket(tmpdir):
    """Test Job.abort() with closed socket."""
    _make_lease(tmpdir, 123)
    with _abort_socket(tmpdir, 123) as proc:
        proc.terminate()
        proc.wait()
        expired = list(leasing.leases_iter(str(tmpdir)))
        assert len(expired) > 0
        for job in expired:
            with pytest.raises(socket.error):
                job.abort()


@pytest.fixture
def end_time():
    """Mock out time.time to return a time in the future."""
    with mock.patch('time.time', return_value=_THE_END) as t:
        yield t


@contextlib.contextmanager
def _make_locked_lease(tmpdir, job_id):
    """Make a locked lease file.

    As a context manager, returns the path to the lease file when
    entering.

    This uses a slow subprocess; any test that uses this should be
    marked slow.
    """
    path = _make_lease(tmpdir, job_id)
    with _lock_lease(path):
        yield path


@contextlib.contextmanager
def _lock_lease(path):
    """Lock a lease file.

    This uses a slow subprocess; any test that uses this should be
    marked slow.
    """
    with subprocess32.Popen(
            [sys.executable, '-um',
             'lucifer.cmd.test.fcntl_lock', path],
            stdout=subprocess32.PIPE) as proc:
        # Wait for lock grab.
        proc.stdout.readline()
        try:
            yield
        finally:
            proc.terminate()


@contextlib.contextmanager
def _abort_socket(tmpdir, job_id):
    """Open a testing abort socket and listener for a job.

    As a context manager, returns the Popen instance for the listener
    process when entering.

    This uses a slow subprocess; any test that uses this should be
    marked slow.
    """
    path = os.path.join(str(tmpdir), '%d.sock' % job_id)
    logger.debug('Making abort socket at %s', path)
    with subprocess32.Popen(
            [sys.executable, '-um',
             'lucifer.cmd.test.abort_socket', path],
            stdout=subprocess32.PIPE) as proc:
        # Wait for socket bind.
        proc.stdout.readline()
        try:
            yield proc
        finally:
            proc.terminate()


def _make_lease(tmpdir, job_id):
    return _make_lease_file(str(tmpdir), job_id)


def _make_lease_file(jobdir, job_id):
    """Make lease file corresponding to a job.

    @param jobdir: job lease file directory
    @param job_id: Job ID
    """
    path = os.path.join(jobdir, str(job_id))
    with open(path, 'w'):
        pass
    return path


class _StubJob(object):
    """Stub for Django Job model."""

    def __init__(self, job_id):
        self.id = job_id
