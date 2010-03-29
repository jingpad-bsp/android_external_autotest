#!/usr/bin/python
#
# Copyright (c) 2010 The Chromium Authors. All rights reserved.
# Use of this source code is governed by a BSD-style license that can be
# found in the LICENSE file.

__author__ = 'kdlucas@chromium.org (Kelly Lucas)'

import logging
import os

from autotest_lib.client.bin import utils, test
from autotest_lib.client.common_lib import error


class platform_NetParms(test.test):
    """
    Verify some of the more important network settings.
    """
    version = 1

    def read_value(self, key, path):
        """
        Find and return values held in path identified by key.

        Args:
            key: identifier of network setting.
            path: pathname where key is located.
        Returns:
            value found in path. If it's a number we'll convert to integer.
        """

        pathname = os.path.join(path, key)
        output = utils.read_one_line(pathname)
        try:
            value = int(output)
        except:
            value = output

        return value

    def run_once(self):
        errors = 0

        coreref = {'path': '/proc/sys/net/core',
                   'message_burst': 10,
                   'message_cost': 5,
                   'netdev_max_backlog': 1000,
                   'optmem_max': 10240,
                   'rmem_default': 110592,
                   'rmem_max': 131071,
                   'wmem_default': 110592,
                   'wmem_max': 131071,
                 }
        ipv4ref = {'path': '/proc/sys/net/ipv4',
                   'icmp_echo_ignore_all': 0,
                   'icmp_echo_ignore_broadcasts': 1,
                   'icmp_ratelimit': 1000,
                   'icmp_ratemask': 6168,
                   'ip_default_ttl': 64,
                   'ip_forward': 0,
                   'tcp_fin_timeout': 60,
                   'tcp_keepalive_probes': 9,
                   'tcp_keepalive_time': 7200,
                   'tcp_retries1': 3,
                   'tcp_retries2': 15,
                   'tcp_syn_retries': 5,
                   'tcp_tw_recycle': 0,
                   'tcp_tw_reuse': 0,
                  }
        unix = {'path': '/proc/sys/net/unix',
                'max_dgram_qlen': 10,
               }
        refs = [coreref, ipv4ref, unix]

        for ref in refs:
            for k in ref:
                if k != 'path':
                    value = self.read_value(k, ref['path'])
                    if value != ref[k]:
                        logging.warn('%s is %d' % (k, value))
                        logging.warn('%s should be %d' % (k, ref[k]))
                        errors += 1

        # If self.error is not zero, there were errors.
        if errors > 0:
            raise error.TestFail('Found %d incorrect values' % errors)
