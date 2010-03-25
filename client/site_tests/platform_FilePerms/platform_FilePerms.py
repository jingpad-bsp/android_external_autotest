#!/usr/bin/python
#
# Copyright (c) 2010 The Chromium Authors. All rights reserved.
# Use of this source code is governed by a BSD-style license that can be
# found in the LICENSE file.

__author__ = 'kdlucas@chromium.org (Kelly Lucas)'

import logging
import os
import re
import stat
import subprocess

from autotest_lib.client.bin import utils, test
from autotest_lib.client.common_lib import error

class platform_FilePerms(test.test):
    """
    Test file permissions.
    """
    version = 1
    mtab_path = '/etc/mtab'
    mount_path = '/bin/mount'


    def checkid(self, fs, userid):
        """
        Check that the uid and gid for fs match userid.

        Args:
            fs: string, directory or file path.
            userid: userid to check for.
        Returns:
            int, the number errors (non-matches) detected.
        """
        errors = 0

        uid = os.stat(fs)[stat.ST_UID]
        gid = os.stat(fs)[stat.ST_GID]

        if userid != uid:
            errors += 1
        if userid != gid:
            errors += 1

        return errors


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


    def read_mtab(self):
        """
        Helper function to read the mtab file into a dict

        Args:
          (none)
        Returns:
          dict, mount points as keys, and another dict with
          options list, device and type as values.
        """
        file_handle = open(self.mtab_path, 'r')
        lines = file_handle.readlines()
        file_handle.close()

        comment_re = re.compile("#.*$")
        mounts = {}
        for line in lines:
            # remove any comments first
            line = comment_re.sub("", line)
            fields = line.split()
            # ignore malformed lines
            if len(fields) < 4:
                continue
            # Don't include rootfs in the list, because it maps to the
            # same location as /dev/root: '/' (and we don't care about
            # its options at the moment).
            if fields[0] == 'rootfs':
                continue
            mounts[fields[1]] = {'device': fields[0],
                                 'type': fields[2],
                                 'options': fields[3].split(',')}
        return mounts


    def try_write(self, fs):
        """
        Try to write a file in the given filesystem.

        Args:
            fs: string, file system to use.
        Returns:
            int, number of errors encountered:
            0 = write successful,
            >0 = write not successful.
        """

        TEXT = 'This is filler text for a test file.\n'

        tempfile = os.path.join(fs, 'test')
        try:
            fh = open(tempfile, 'w')
            fh.write(TEXT)
            fh.close()
        except OSError: # This error will occur with read only filesystem.
            return 1
        except IOError, e:
            return 1

        if os.path.exists(tempfile):
            os.remove(tempfile)

        return 0


    def check_mounted_read_only(self, filesystem):
        """
        Check the permissions of a filesystem according to /etc/mtab.

        Args:
            filesystem: string, file system device to check.
        Returns:
            1 if rw, 0 if ro
        """

        errors = 0
        mtab = self.read_mtab()
        if not (filesystem in mtab.keys()):
            logging.warn('Did not find filesystem %s in mtab' % filesystem)
            errors += 1
            return errors # no point in continuing this test.
        if not ('ro' in mtab[filesystem]['options']):
            logging.warn('Filesystem "%s" is not mounted read only!' %
                         filesystem)
            errors += 1
        return errors


    def check_mount_setup(self):
        """
        Check to make sure that mount shows the same mount points and
        options as /etc/mtab, and that /etc/mtab is a symlink to
        /proc/mount.

        Args:
            (none)
        Returns:
            int, Number of errors encountered.
        """

        # Call mount, and compare output to /etc/mtab entries.
        mount_call = subprocess.Popen([self.mount_path],
                                      stdout=subprocess.PIPE,
                                      stderr=subprocess.PIPE)
        (out, err) = mount_call.communicate();
        mount_lines = out.split("\n");
        mounts = {}
        for line in mount_lines:
            fields = line.split()
            # Skip empty/non-conforming lines.
            if (len(fields) >= 6):
                mounts[fields[2]] = {
                    'device': fields[0],
                    'type': fields[4],
                    'options': fields[5].strip("()").split(','),
                    }
        # Compare the filesystems to make sure that what mount
        # reports, and what's in the config file are identical in both
        # the mounts that exist, and the options that are set.  Note
        # that this test allows there to be listings in mtab that are
        # not currently mounted.
        errors = 0
        mtab = self.read_mtab()
        for filesystem in mounts.keys():
            if not (filesystem in mtab.keys()):
                logging.warn('Mounted filesystem %s not found in mtab.' %
                             filesystem)
                errors += 1
            for option in mounts[filesystem]['options']:
                if not (option in mtab[filesystem]['options']):
                    logging.warn('Mounted filesystem %s has option %s '
                                 'that is not listed in mtab.' %
                                 (filesystem, option))
                    errors +=1
            for option in mtab[filesystem]['options']:
                if not (option in mounts[filesystem]['options']):
                    logging.warn('Mounted filesystem %s does not have '
                                 'option %s that is listed in mtab.' %
                                 (filesystem, option))
                    errors +=1

        # Now we just make sure that /etc/mtab is a symlink to /proc/mounts
        mtab_link = os.readlink("/etc/mtab")
        if mtab_link != "/proc/mounts":
            logging.warn('Symbolic link /etc/mtab points to "%s" instead of '
                         '/proc/mounts.' % mtab_link)
            errors += 1
        return errors


    def check_mount_options(self):
        """
        Check the permissions of all non-rootfs filesystems to make
        sure they have the right mount options.

        Skips the root filesystem, and allows "/dev" to be missing
        "nodev".

        Args:
            (none)
        Returns:
            int, number of filesystems with the wrong options.
        """
        errors = 0

        mtab = self.read_mtab()
        for filesystem in mtab.keys():
            # skip the rootfs mounts, because it needs to have all
            # three attributes (exec, suid, and dev).
            if filesystem == "/":
                continue
            for option in ['noexec', 'nosuid', 'nodev']:
                # Let the /dev partition have dev nodes (duh!)
                if option == "nodev" and filesystem == "/dev":
                    continue
                if not (option in mtab[filesystem]['options']):
                    logging.warn("%s partition doesn't have option %s set" %
                                 (filesystem, option))
                    errors += 1
        return errors


    def run_once(self):
        """
        Main testing routine for platform_FilePerms.
        """
        errors = 0

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

        errors += self.check_mounted_read_only('/')

        # Check mount options on mount points.
        errors += self.check_mount_options()

        # Check that /bin/mount output and mtab jive,
        # and that mtab is a symbolic link to /dev/mounts.
        errors += self.check_mount_setup()

        # If errors is not zero, there were errors.
        if errors > 0:
            raise error.TestFail('Found %d permission errors' % errors)
