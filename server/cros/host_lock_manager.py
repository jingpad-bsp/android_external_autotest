# Copyright (c) 2012 The Chromium OS Authors. All rights reserved.
# Use of this source code is governed by a BSD-style license that can be
# found in the LICENSE file.

import logging

import common
from autotest_lib.client.common_lib import error
from autotest_lib.server.cros import frontend_wrappers

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
        self._hosts = frozenset()
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


    def _host_modifier(self, **kwargs):
        """Helper that runs the modify_host() RPC with specified args.

        Passes kwargs through to the RPC directly.
        """
        self._afe.run('modify_hosts',
                      host_filter_data={'hostname__in': list(self._hosts)},
                      update_data=kwargs)
