#!/usr/bin/python
#
# Copyright (c) 2010 The Chromium Authors. All rights reserved.
# Use of this source code is governed by a BSD-style license that can be
# found in the LICENSE file.

"""
This testcase exercises the file system by ensuring we can copy a sufficient
number of files into one directory, in this case will create 100,000 files.
"""

__author__ = 'kdlucas@chromium.org (Kelly Lucas)'

import commands
import logging
import os
import sys
import shutil

from autotest_lib.client.bin import utils, test
from autotest_lib.client.common_lib import error


class platform_FileNum(test.test):
    """
    Test file number limitations per directory.
    """
    version = 1

    def create_files(self, targetdir, fqty):
        """
        Create the number of files specified by fqty into targetdir.

        Args:
            targetdir: string, directory to create files in.
            fqty: quantity of files to create.
        Returns:
            int, quantity of verified files created.
        """
        TEXT = 'ChromeOS rocks with fast response and low maintenance costs!\n'
        f_dir1 = os.path.join(targetdir, 'createdir')
        f_dir2 = os.path.join(targetdir, 'copydir')
        if not os.path.exists(f_dir1):
            try:
                os.makedirs(f_dir1)
            except IOError, e:
                logging.warn('Error making directory %s\n%s' % (f_dir1, e))
                raise error.TestFail(e)
        if not os.path.exists(f_dir2):
            try:
                os.makedirs(f_dir2)
            except IOError, e:
                logging.warn('Error making directory %s\n%s' % (f_dir2, e))
                raise error.TestFail(e)

        for i in range(fqty):
            # Create one file in f_dir1 and copy it to f_dir2
            file1 = os.path.join(f_dir1, '%s.txt' % str(i))
            file2 = os.path.join(f_dir2, '%s.txt' % str(i))
            try:
                fh = file(file1, 'w')
                fh.write(TEXT)
                fh.close()
            except IOError, e:
                logging.warn('Error creating file %s\n%s' % (file1, e))
                raise error.TestFail(e)
            try:
                shutil.copyfile(file1, file2)
            except IOError, e:
                logging.warn('Error copying file %s\n%s' % (file1, e))
                raise error.TestFail(e)

        total_created = len(os.listdir(f_dir1))
        total_copied = len(os.listdir(f_dir2))
        if total_created != (fqty) or total_copied != (fqty):
            logging.warn('Number of files requested: %s' % fqty)
            logging.warn('Number of files created: %s' % total_created)
            logging.warn('Number of files copied: %s' % total_copied)
            raise error.TestFail('Number of files is not correct!')

        shutil.rmtree(f_dir1)
        shutil.rmtree(f_dir2)

        return total_created

    def run_once(self):
        reqdir = ['/mnt/stateful_partition', '/tmp']
        reqnum = [100000, 1000]

        for i in range(2):
            filenum = self.create_files(reqdir[i], reqnum[i])
            if filenum != reqnum[i]:
                raise error.TestFail('File qty in %s is incorrect!' % reqdir[i])
