# Copyright (c) 2012 The Chromium OS Authors. All rights reserved.
# Use of this source code is governed by a BSD-style license that can be
# found in the LICENSE file.

from autotest_lib.server.hosts.chromiumos_host import SiteHost


def make_ssh_command(user='root', port=22, opts='', hosts_file=None,
                     connect_timeout=None, alive_interval=None):
    """Override default make_ssh_command to use options tuned for Chrome OS.

    Tuning changes:
      - ConnectTimeout=30; maximum of 30 seconds allowed for an SSH connection
      failure.  Consistency with remote_access.sh.

      - ServerAliveInterval=180; which causes SSH to ping connection every
      180 seconds. In conjunction with ServerAliveCountMax ensures that if the
      connection dies, Autotest will bail out quickly. Originally tried 60 secs,
      but saw frequent job ABORTS where the test completed successfully.

      - ServerAliveCountMax=3; consistency with remote_access.sh.

      - ConnectAttempts=4; reduce flakiness in connection errors; consistency
      with remote_access.sh.

      - UserKnownHostsFile=/dev/null; we don't care about the keys. Host keys
      change with every new installation, don't waste memory/space saving them.

      - SSH protocol forced to 2; needed for ServerAliveInterval.
    """
    base_command = ('/usr/bin/ssh -a -x %s -o StrictHostKeyChecking=no'
                    ' -o UserKnownHostsFile=/dev/null -o BatchMode=yes'
                    ' -o ConnectTimeout=30 -o ServerAliveInterval=180'
                    ' -o ServerAliveCountMax=3 -o ConnectionAttempts=4'
                    ' -o Protocol=2 -l %s -p %d')
    return base_command % (opts, user, port)
