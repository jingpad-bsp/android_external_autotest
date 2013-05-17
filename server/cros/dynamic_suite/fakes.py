#pylint: disable-msg=C0111
# Copyright (c) 2012 The Chromium OS Authors. All rights reserved.
# Use of this source code is governed by a BSD-style license that can be
# found in the LICENSE file.

"""Fakes for dynamic_suite-related unit tests."""


class FakeControlData(object):
    """A fake parsed control file data structure."""
    def __init__(self, suite, data, time='LONG', expr=False,
                 dependencies=None):
        self.string = 'text-' + data
        self.name = 'name-' + data
        self.path = None  # Will be set during 'parsing'.
        self.data = data
        self.suite = suite
        self.test_type = 'Client'
        self.experimental = expr
        if not dependencies:
            dependencies=[]
        self.dependencies = dependencies
        self.time = time
        self.retries = 0


class FakeJob(object):
    """Faked out RPC-client-side Job object."""
    def __init__(self, id=0, statuses=[], hostnames=[]):
        self.id = id
        self.hostnames = hostnames if hostnames else ['host%d' % id]
        self.owner = 'tester'
        self.name = 'Fake Job %d' % self.id
        self.statuses = statuses


class FakeHost(object):
    """Faked out RPC-client-side Host object."""
    def __init__(self, hostname='', status='Ready', locked=False, locked_by=''):
        self.hostname = hostname
        self.status = status
        self.locked = locked
        self.locked_by = locked_by


    def __str__(self):
        return '%s: %s.  %s%s' % (
            self.hostname, self.status,
            'Locked' if self.locked else 'Unlocked',
            ' by %s' % self.locked_by if self.locked else '')


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
    def __init__(self, code, name, reason, aborted=None, hostname=None):
        self.status = code
        self.test_name = name
        self.reason = reason
        self.hostname = hostname if hostname else 'hostless'
        self.entry = {}
        self.test_started_time = '2012-11-11 11:11:11'
        self.test_finished_time = '2012-11-11 12:12:12'
        if aborted:
            self.entry['aborted'] = True
        if hostname:
            self.entry['host'] = {'hostname': hostname}


    def __repr__(self):
        return '%s\t%s\t%s: %s' % (self.status, self.test_name, self.reason,
                                   self.hostname)


    def equals_record(self, status):
        """Compares this object to a recorded status."""
        if 'aborted' in self.entry and self.entry['aborted']:
            return status._status == 'ABORT'
        return (self.status == status._status and
                status._test_name.endswith(self.test_name) and
                self.reason == status._reason)


    def equals_hostname_record(self, status):
        """Compares this object to a recorded status.

        Expects the test name field of |status| to contain |self.hostname|.
        """
        return (self.status == status._status and
                self.hostname in status._test_name and
                self.reason == status._reason)


    def record_all(self, record):
        pass


    def is_good(self):
        pass

    def name(self):
        return self.test_name
