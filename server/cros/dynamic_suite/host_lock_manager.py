# Copyright (c) 2012 The Chromium OS Authors. All rights reserved.
# Use of this source code is governed by a BSD-style license that can be
# found in the LICENSE file.

import logging
import signal

import common
from autotest_lib.client.common_lib import error
from autotest_lib.server.cros.dynamic_suite import frontend_wrappers

"""HostLockManager class, for the dynamic_suite module.

A HostLockManager instance manages locking and unlocking a set of
autotest DUTs.  Once a host is added to the managed set, it cannot be
removed.  If the caller fails to unlock() locked hosts before the
instance is destroyed, it will attempt to unlock() the hosts
automatically, but this is to be avoided.

Usage:
  manager = host_lock_manager.HostLockManager()
  try:
      manager.add(['host1'])
      manager.lock()
      # do things
  finally:
      manager.unlock()
"""

class HostLockManager(object):
    """
    @var _afe: an instance of AFE as defined in server/frontend.py.
    @var _hosts: an iterable of DUT hostnames.
    @var _hosts_are_locked: whether we believe the hosts are locked
    """


    def __init__(self, afe=None):
        """
        Constructor

        @param afe: an instance of AFE as defined in server/frontend.py.
        """
        self._afe = afe or frontend_wrappers.RetryingAFE(timeout_min=30,
                                                         delay_sec=10,
                                                         debug=False)
        self._hosts = set()
        self._hosts_are_locked = False


    def __del__(self):
        if self._hosts_are_locked:
            logging.error('Caller failed to unlock %r!  '
                          'Forcing unlock now.' % self._hosts)
            self.unlock()


    def add(self, hosts):
        """Permanently associate this instance with |hosts|.

        @param hosts: iterable of hostnames to take over locking/unlocking.
        """
        self._hosts = self._hosts.union(hosts)


    def lock(self):
        """Lock all DUTs in self._hosts."""
        self._host_modifier(locked=True)
        self._hosts_are_locked = True


    def unlock(self):
        """Unlock all DUTs in self._hosts."""
        self._host_modifier(locked=False)
        self._hosts_are_locked = False
        self._hosts = set()


    def lock_one_host(self, host):
        """Attemps to lock one host if it's not already locked.

        @param host: a string, hostname.
        @returns a boolean: False == host is already locked.
        """
        mod_host = host.split('.')[0]
        host_info = self._afe.get_hosts(hostname=mod_host)
        if not host_info:
            logging.error('Skip unknown host %s.', host)
            return False

        host_info = host_info[0]
        if host_info.locked:
            err = ('Contention detected: %s is locked by %s at %s.' %
                   (mod_host, host_info.locked_by, host_info.lock_time))
            logging.error(err)
            return False

        self.add([mod_host])
        self.lock()
        return True


    def _host_modifier(self, **kwargs):
        """Helper that runs the modify_host() RPC with specified args.

        Passes kwargs through to the RPC directly.
        """
        self._afe.run('modify_hosts',
                      host_filter_data={'hostname__in': list(self._hosts)},
                      update_data=kwargs)


class HostsLockedBy(object):
    """Context manager to make sure that a HostLockManager will always unlock
    its machines. This protects against both exceptions and SIGTERM."""

    def _make_handler(self):
        def _chaining_signal_handler(signal_number, frame):
            self._manager.unlock()
            # self._old_handler can also be signal.SIG_{IGN,DFL} which are ints.
            if callable(self._old_handler):
                self._old_handler(signal_number, frame)
        return _chaining_signal_handler


    def __init__(self, manager):
        """
        @param manager: The HostLockManager used to lock the hosts.
        """
        self._manager = manager
        self._old_handler = signal.SIG_DFL


    def __enter__(self):
        self._old_handler = signal.signal(signal.SIGTERM, self._make_handler())


    def __exit__(self, exntype, exnvalue, backtrace):
        signal.signal(signal.SIGTERM, self._old_handler)
        self._manager.unlock()
