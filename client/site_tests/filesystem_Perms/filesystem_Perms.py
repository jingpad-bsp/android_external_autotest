#!/usr/bin/python
#
# Copyright (c) 2010 The Chromium Authors. All rights reserved.
# Use of this source code is governed by a BSD-style license that can be
# found in the LICENSE file.

__author__ = 'kdlucas@chromium.org (Kelly Lucas)'

import os
import stat

from autotest_lib.client.bin import utils, test
from autotest_lib.client.common_lib import error


class filesystem_Perms(test.test):
    """
    Test file permissions.
    """
    version = 1

    def get_perm(self, filesystem):
        """
        Check the file permissions of filesystem.

        Args:
            filesystem: string, mount point for filesystem to check.
        Returns:
            int, equivalent to unix permissions.
        """
        mask = 0777

        fstat = os.stat(filesystem)
        mode = fstat[stat.ST_MODE]

        fperm = oct(mode & mask)
        return fperm

    def get_mtab(self, filesystem):
        """
        Check the permissions of a filesystem according to /etc/mtab.

        Args:
            filesystem: string, file system device to check.
        Returns:
            True if rw, False if ro
        """

        mtabpath = '/etc/mtab'
        fh = open(mtabpath, 'r')
        mtablist = fh.readlines()
        fh.close()

        for line in mtablist:
            if filesystem in line:
                mtabfields = line.split()
                mtaboptions = mtabfields[3].split(',')
                if mtaboptions[0] == 'ro':
                    return False
                return True
        # In case we get here, it means we didn't find it, so return false.
        raise error.TestFail('Didn't find  %s in %s' % (filesystem, mtabpath))

    def run_once(self):
        reqdir = ['/', '/mnt/stateful_partition', '/tmp']
        perms = ['0755', '0755', '0777']
        rootfs = '/dev/root'

        for i in range(3):
            fperms = self.get_perm(reqdir[i])
            if fperms != perms[i]:
                error.Warning('%s has %s permissions' % (reqdir[i], fperms))
                raise error.TestFail('Permissions error with %s' % reqdir[i])

        if self.get_mtab(rootfs):
            raise error.TestFail('Root filesystem is not mounted read only!')
