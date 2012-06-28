# Copyright (c) 2012 The Chromium OS Authors. All rights reserved.
# Use of this source code is governed by a BSD-style license that can be
# found in the LICENSE file.

"""Fakes for dynamic_suite-related unit tests."""


class FakeControlData(object):
    """A fake parsed control file data structure."""
    def __init__(self, suite, data, expr=False):
        self.string = 'text-' + data
        self.name = 'name-' + data
        self.data = data
        self.suite = suite
        self.test_type = 'Client'
        self.experimental = expr


class FakeJob(object):
    """Faked out RPC-client-side Job object."""
    def __init__(self, id=0, statuses=[]):
        self.id = id
        self.hostname = 'host%d' % id
        self.owner = 'tester'
        self.name = 'Fake Job %d' % self.id
        self.statuses = statuses


class FakeHost(object):
    """Faked out RPC-client-side Host object."""
    def __init__(self, status='Ready'):
        self.status = status

class FakeLabel(object):
    """Faked out RPC-client-side Label object."""
    def __init__(self, id=0):
        self.id = id


class FakeStatus(object):
    """Fake replacement for server-side job status objects.

    @var status: 'GOOD', 'FAIL', 'ERROR', etc.
    @var test_name: name of the test this is status for
    @var reason: reason for failure, if any
    @var aborted: present and True if the job was aborted.  Optional.
    """
    def __init__(self, code, name, reason, aborted=None):
        self.status = code
        self.test_name = name
        self.reason = reason
        self.entry = {}
        self.test_started_time = '2012-11-11 11:11:11'
        self.test_finished_time = '2012-11-11 12:12:12'
        if aborted:
            self.entry['aborted'] = True

    def equals_record(self, status):
        """Compares this object to a recorded status."""
        return self._equals_record(status._status, status._test_name,
                                   status._reason)

    def _equals_record(self, status, name, reason=None):
        """Compares this object and fields of recorded status."""
        if 'aborted' in self.entry and self.entry['aborted']:
            return status == 'ABORT'
        return (self.status == status and
                self.test_name == name and
                self.reason == reason)
