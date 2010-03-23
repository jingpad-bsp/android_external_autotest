#!/usr/bin/python
#
# Copyright (c) 2010 The Chromium Authors. All rights reserved.
# Use of this source code is governed by a BSD-style license that can be
# found in the LICENSE file.

__author__ = 'kdlucas@chromium.org (Kelly Lucas)'

import logging
import os
import stat

from autotest_lib.client.bin import utils, test
from autotest_lib.client.common_lib import error


class platform_FilePerms(test.test):
    """
    Test file permissions.
    """
    version = 1

    def get_perm(self, fs):
        """
        Check the file permissions of filesystem.

        Args:
            fs: string, mount point for filesystem to check.
        Returns:
            int, equivalent to unix permissions.
        """
        MASK = 0777

        fstat = os.stat(fs)
        mode = fstat[stat.ST_MODE]

        fperm = oct(mode & MASK)
        return fperm

    def get_rw_mount_status(self, fs):
        """
        Check the permissions of a filesystem according to /etc/mtab.

        Args:
            fs: string, file system device to check.
        Returns:
            True if rw, False if ro
        """

        mtabpath = '/etc/mtab'
        fh = open(mtabpath, 'r')
        mtablist = fh.readlines()
        fh.close()

        for line in mtablist:
            if fs in line:
                mtabfields = line.split()
                mtaboptions = mtabfields[3].split(',')
                if mtaboptions[0] == 'ro':
                    return False
                return True
        # In case we get here, it means we didn't find it, so return false.
        raise error.TestFail('Did not find  %s in %s' % (fs, mtabpath))

    def try_write(self, fs):
        """
        Try to write a file in the given filesystem.

        Args:
            fs: string, file system to use.
        Returns:
            boolean, True = write successful, False = write not successful.
        """

        TEXT = 'This is filler text for a test file.\n'

        tempfile = os.path.join(fs, 'test')
        try:
            fh = open(tempfile, 'w')
            fh.write(TEXT)
            fh.close()
        except OSError: # This error will occur with read only filesystem.
            return False
        except IOError, e:
            return False

        if os.path.exists(tempfile):
            os.remove(tempfile)

        return True

    def checkid(self, fs, userid):
        """
        Check that the uid and gid for fs match userid.

        Args:
            fs: string, directory or file path.
            userid: userid to check for.
        Returns:
            boolean, True = match, False = did not match.
        """
        status = True

        uid = os.stat(fs)[stat.ST_UID]
        gid = os.stat(fs)[stat.ST_GID]

        if userid != uid:
            status = False
        if userid != gid:
            status = False

        return status

    def run_once(self):
        errors = 0
        rootfs = '/dev/root'

        # Root owned directories with expected permissions.
        root_dirs = {'/': '0755',
                     '/bin': '0755',
                     '/boot': '0755',
                     '/dev': '0755',
                     '/etc': '0755',
                     '/home': '0755',
                     '/lib': '0755',
                     '/media': '0777',
                     '/mnt': '0755',
                     '/mnt/stateful_partition': '0755',
                     '/opt': '0755',
                     '/proc': '0555',
                     '/sbin': '0755',
                     '/sys': '0755',
                     '/tmp': '0777',
                     '/usr': '0755',
                     '/usr/bin': '0755',
                     '/usr/lib': '0755',
                     '/usr/local': '0755',
                     '/usr/sbin': '0755',
                     '/usr/share': '0755',
                     '/var': '0755',
                     '/var/cache': '0755'}

        # Read-only directories
        ro_dirs = ['/', '/bin', '/boot', '/etc', '/lib', '/mnt',
                   '/opt', '/sbin', '/usr', '/usr/bin', '/usr/lib',
                   '/usr/local', '/usr/sbin', '/usr/share', '/var',
                   '/var/lib', '/var/local']

        # Root directories writable by root
        root_rw_dirs = ['/var/cache', '/var/log']

        # Ensure you cannot write files in read only directories.
        for dir in ro_dirs:
            if self.try_write(dir):
                errors += 1

        # Ensure the uid and gid are correct for root owned directories.
        for dir in root_dirs:
          if not self.checkid(dir, 0):
                errors += 1

        # Ensure root can write into root dirs with rw access.
        for dir in root_rw_dirs:
            if not self.try_write(dir):
                logging.warn('Root cannot write in %s' % dir)
                errors += 1

        # Check permissions on root owned directories.
        for dir in root_dirs:
            fperms = self.get_perm(dir)
            if fperms != root_dirs[dir]:
                logging.warn('%s has %s permissions' % (dir, fperms))
                errors += 1

        if self.get_rw_mount_status(rootfs):
            logging.warn('Root filesystem is not mounted read only!')
            errors += 1

        # If errors is not zero, there were errors.
        if errors > 0:
            raise error.TestFail('Found %d permission errors' % errors)
