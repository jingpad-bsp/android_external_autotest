# Copyright 2017 The Chromium Authors. All rights reserved.
# Use of this source code is governed by a BSD-style license that can be
# found in the LICENSE file.

from __future__ import absolute_import
from __future__ import division
from __future__ import print_function

import contextlib
import os
import sys

import mock
import subprocess32

from lucifer import leasing


def test_get_expired_leases(tmpdir):
    """Test get_expired_leases()."""
    _make_lease(tmpdir, 123)
    with _make_locked_lease(tmpdir, 124):
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


@contextlib.contextmanager
def _make_locked_lease(tmpdir, job_id):
    path = _make_lease(tmpdir, job_id)
    with _lock_lease(path):
        yield path


@contextlib.contextmanager
def _lock_lease(path):
    with subprocess32.Popen(
            [sys.executable, '-um',
             'lucifer.scripts.fcntl_lock', path],
            stdout=subprocess32.PIPE) as proc:
        # Wait for lock grab.
        proc.stdout.readline()
        try:
            yield
        finally:
            proc.terminate()


def _make_lease(tmpdir, job_id):
    return leasing.make_lease_file(str(tmpdir), job_id)


class _StubJob(object):

    def __init__(self, job_id):
        self.id = job_id
