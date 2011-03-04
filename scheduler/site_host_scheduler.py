# Copyright (c) 2011 The Chromium OS Authors. All rights reserved.
# Use of this source code is governed by a BSD-style license that can be
# found in the LICENSE file.

import random
from autotest_lib.client.common_lib import error
from autotest_lib.scheduler import scheduler_models
from autotest_lib.scheduler.host_scheduler import BaseHostScheduler
from autotest_lib.server import hosts


class site_host_scheduler(BaseHostScheduler):
    """Extends BaseHostScheduler to randomize host list and add an SSH check."""

    # SSH connection timeout. Since this is happening in the scheduler, we don't
    # want to wait very long to verify a host.
    _SSH_TIMEOUT = 5


    def hosts_in_label(self, label_id):
        """Override method to randomize host order.

        hosts_in_label returns a set(), but sets are not random, rather
        arbitrarily ordered. We need the set to be truly randomized so tests are
        distributed evenly across the host pool.
        """
        hosts = list(super(site_host_scheduler, self).hosts_in_label(label_id))
        random.shuffle(hosts)
        return set(hosts)


    def is_host_usable(self, host_id):
        """Override method to add an SSH check for host usability.

        We don't want to schedule against any hosts which are not reachable.
        """
        if not super(site_host_scheduler, self).is_host_usable(host_id):
            return False

        host_data = scheduler_models.Host(id=host_id)
        host = hosts.SSHHost(host_data.hostname)

        try:
            host.ssh_ping(timeout=self._SSH_TIMEOUT)
        except error.AutoservError:
            return False

        return True
