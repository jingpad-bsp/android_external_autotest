# Copyright 2016 The Chromium OS Authors. All rights reserved.
# Use of this source code is governed by a BSD-style license that can be
# found in the LICENSE file.

import logging
import socket

import common
from autotest_lib.client.common_lib import hosts
from autotest_lib.server import utils


class SshVerifier(hosts.Verifier):
    """
    Verifier to test a host's accessibility via `ssh`.

    This verifier checks whether a given host is reachable over `ssh`.
    In the event of failure, it distinguishes one of three distinct
    conditions:
      * The host can't be found with a DNS lookup.
      * The host doesn't answer to ping.
      * The host answers to ping, but not to ssh.
    """

    def verify(self, host):
        if host.is_up():
            return
        msg = 'No answer to ssh from %s'
        try:
            socket.gethostbyname(host.hostname)
        except Exception as e:
            logging.exception('DNS lookup failure')
            msg = 'Unable to look up %%s in DNS: %s' % e
        else:
            if utils.ping(host.hostname, tries=1, deadline=1) != 0:
                msg = 'No answer to ping from %s'
        raise hosts.AutotestHostVerifyError(msg % host.hostname)


    @property
    def description(self):
        return 'host is available via ssh'
