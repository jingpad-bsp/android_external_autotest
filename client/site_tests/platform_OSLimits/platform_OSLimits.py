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


class platform_OSLimits(test.test):
    """
    Verify os limitations are set to correct levels.
    """
    version = 1

    def get_limit(self, key, path):
        """
        Find and return values held in path.

        Args:
            key: dictionary key of os limit.
            path: pathname of file with current value.
        Returns:
            value found in path. If it's a number we'll convert to integer.
        """

        value = None
        # Most files have only one value, but if there are multiple values we
        # will handle it differently. Determine this from the key.

        multivals = ['max_open', 'max_procs']
        limits = {'max_open': 'Max open files',
                  'max_procs': 'Max processes',
                 }

        if key in multivals:
            output = utils.read_file(path)
            lines = output.splitlines()
            for line in lines:
                if limits[key] in line:
                    fields = line.split(limits[key])
                    vals = fields[1].split()
                    value = (vals[0])
        else:
            value = (utils.read_one_line(path))

        if value == 'unlimited':
            return value
        else:
            return int(value)

    def run_once(self):
        errors = 0

        ref_min = {'file_max': 100424,
                   'max_open': 1024,
                   'max_procs': 8000,
                   'max_threads': 16000,
                   'msg_max': 10,
                   'msgsize': 8192,
                   'msg_queue': 256,
                   'ngroups_max': 65536,
                   'nr_open': 1048576,
                   'pid_max': 32768,
                  }

        ref_equal = {'leases': 1,
                     'panic': 0,
                     'sysrq': 1,
                     'suid-dump': 0,
                    }

        refpath = {'file_max': '/proc/sys/fs/file-max',
                   'leases': '/proc/sys/fs/leases-enable',
                   'max_open': '/proc/self/limits',
                   'max_procs': '/proc/self/limits',
                   'max_threads': '/proc/sys/kernel/threads-max',
                   'msg_max': '/proc/sys/fs/mqueue/msg_max',
                   'msgsize': '/proc/sys/fs/mqueue/msgsize_max',
                   'msg_queue': '/proc/sys/fs/mqueue/queues_max',
                   'ngroups_max': '/proc/sys/kernel/ngroups_max',
                   'nr_open': '/proc/sys/fs/nr_open',
                   'panic': '/proc/sys/kernel/panic',
                   'pid_max': '/proc/sys/kernel/pid_max',
                   'sysrq': '/proc/sys/kernel/sysrq',
                   'suid-dump': '/proc/sys/fs/suid_dumpable',
                  }

        # Create osvalue dictionary with the same keys as refpath.
        osvalue = {}
        for k in refpath:
            osvalue[k] = None

        for key in ref_min:
            osvalue[key] = self.get_limit(key, refpath[key])
            if osvalue[key] < ref_min[key]:
                logging.warn('%s is %d' % (refpath[key], osvalue[key]))
                logging.warn('%s should be at least %d' % (refpath[key],
                             ref_min[key]))
                errors += 1

        for key in ref_equal:
            osvalue[key] = self.get_limit(key, refpath[key])
            if osvalue[key] != ref_equal[key]:
                logging.warn('%s is set to %d' % (refpath[key], osvalue[key]))
                logging.warn('Expected %d' % ref_equal[key])
                errors += 1

        # If self.error is not zero, there were errors.
        if errors > 0:
            raise error.TestFail('Found %d incorrect values' % errors)
