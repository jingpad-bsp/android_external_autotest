# Copyright 2017 The Chromium Authors. All rights reserved.
# Use of this source code is governed by a BSD-style license that can be
# found in the LICENSE file.

from __future__ import absolute_import
from __future__ import division
from __future__ import print_function

import contextlib
import logging
import os
import sys

import mock
import pytest
import subprocess32

from lucifer import leasing

logger = logging.getLogger(__name__)


@pytest.mark.slow
def test_get_expired_leases(tmpdir):
    """Test get_expired_leases()."""
    _make_lease(tmpdir, 123)
    with _make_locked_lease(tmpdir, 124):
        got = list(leasing.get_expired_leases(str(tmpdir)))
    assert all(isinstance(job, leasing.JobLease) for job in got)
    assert [job.id for job in got] == [123]


def test_get_expired_leases_with_sock_files(tmpdir):
    """Test get_expired_leases()."""
    _make_lease(tmpdir, 123)
    tmpdir.join('123.sock').write('')
    got = list(leasing.get_expired_leases(str(tmpdir)))
    assert all(isinstance(job, leasing.JobLease) for job in got)
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

    assert all(isinstance(job, leasing.JobLease) for job in got)
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

    assert all(isinstance(job, leasing.JobLease) for job in got)
    assert 123 in [job.id for job in got]
    assert 124 not in [job.id for job in got]


def test_Job_cleanup(tmpdir):
    """Test Job.cleanup()."""
    path = _make_lease(tmpdir, 123)
    for job in leasing.get_expired_leases(str(tmpdir)):
        job.cleanup()
    assert not os.path.exists(path)


@pytest.mark.slow
def test_Job_abort(tmpdir):
    """Test Job.abort()."""
    _make_lease(tmpdir, 123)
    with _abort_socket(tmpdir, 123) as proc:
        for job in leasing.get_expired_leases(str(tmpdir)):
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
        for job in leasing.get_expired_leases(str(tmpdir)):
            with pytest.raises(Exception):
                job.abort()


@contextlib.contextmanager
def _make_locked_lease(tmpdir, job_id):
    path = _make_lease(tmpdir, job_id)
    with _lock_lease(path):
        yield path


@contextlib.contextmanager
def _lock_lease(path):
    with subprocess32.Popen(
            [sys.executable, '-um',
             'lucifer.scripts.test.fcntl_lock', path],
            stdout=subprocess32.PIPE) as proc:
        # Wait for lock grab.
        proc.stdout.readline()
        try:
            yield
        finally:
            proc.terminate()


@contextlib.contextmanager
def _abort_socket(tmpdir, job_id):
    "Open a testing abort socket and listener for a job."
    path = os.path.join(str(tmpdir), '%d.sock' % job_id)
    logger.debug('Making abort socket at %s', path)
    with subprocess32.Popen(
            [sys.executable, '-um',
             'lucifer.scripts.test.abort_socket', path],
            stdout=subprocess32.PIPE) as proc:
        # Wait for socket bind.
        proc.stdout.readline()
        try:
            yield proc
        finally:
            proc.terminate()


def _make_lease(tmpdir, job_id):
    return leasing.make_lease_file(str(tmpdir), job_id)


class _StubJob(object):

    def __init__(self, job_id):
        self.id = job_id
