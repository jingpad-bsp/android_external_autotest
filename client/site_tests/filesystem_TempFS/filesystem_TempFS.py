#!/usr/bin/python
#
# Copyright (c) 2010 The Chromium Authors. All rights reserved.
# Use of this source code is governed by a BSD-style license that can be
# found in the LICENSE file.

__author__ = 'kdlucas@chromium.org (Kelly Lucas)'

import logging, os

from autotest_lib.client.bin import test, utils
from autotest_lib.client.common_lib import error


class filesystem_TempFS(test.test):
    """
    Test temp file systems.
    """
    version = 1

    def run_once(self):
        errors = 0
        # The minimum available space we expect on temp filesystems: 512mb.
        threshhold = 512000000
        tempdirs = ['/dev', '/tmp', '/dev/shm', '/var/tmp', '/var/run',
                    '/var/lock']

        for dir in tempdirs:
            if os.path.isdir(dir):
                avail = utils.freespace(dir)
                if avail < threshhold:
                    logging.error('Not enough available space on %s' % dir)
                    logging.error('%d bytes is minimum, found %d bytes' %
                                  (threshhold, avail))
                    errors += 1
            else:
                logging.error('%s does not exist!' % dir)
                error += 1

        if errors:
            raise error.TestFail('There were %d temp directory errors' % errors)
