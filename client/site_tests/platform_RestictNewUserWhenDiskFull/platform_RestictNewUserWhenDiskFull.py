# Copyright (c) 2011 The Chromium OS Authors. All rights reserved.
# Use of this source code is governed by a BSD-style license that can be
# found in the LICENSE file.

import datetime
import logging
import math
import os
import time

from autotest_lib.client.bin import utils
from autotest_lib.client.common_lib import error
from autotest_lib.client.cros import cros_ui_test, httpd


class platform_RestictNewUserWhenDiskFull(cros_ui_test.UITest):
    version = 1
    MINIMUM_BLOCK_SIZE = 1048576 # Exactly one megabyte
    DISK_SPACE_BUFFER = 524288 # Exactly half a megabyte
    FOLDER_PATH = '/mnt/stateful_partition/'

    def initialize(self):
        super(platform_RestictNewUserWhenDiskFull,
              self).initialize(creds='$default')

    def start_authserver(self):
        super(platform_RestictNewUserWhenDiskFull, self).start_authserver()

    def cleanup(self):
        super(platform_RestictNewUserWhenDiskFull, self).cleanup()
        delete_path = os.path.join(self.FOLDER_PATH, 'big_file_*')
        utils.system('rm %s' % delete_path)

    def fill_available_disk_space(self, remaining, file_path):
        """Creates a large file that fills the amount of space remaining.

        Args:
            remaining: amount of disk space to fill in bytes
            file_path: name of the file to create

        Returns:
            True if the file was created; False otherwise
        """
        # Adjust how quickly we write the file based on how much space is left
        if (remaining < self.MINIMUM_BLOCK_SIZE):
            # If we are within less than 1MB we don't do anything.
            return False
        for i in range(4):
            bs = self.MINIMUM_BLOCK_SIZE * pow(10, i)
            if remaining < bs:
                bs = self.MINIMUM_BLOCK_SIZE * pow(10, (i - 1))
                break

        # Make sure the byte size fits evenly into the total size of the file.
        count = remaining / bs
        # Create a large file
        utils.system('sudo dd if=/dev/zero of=%s count=%d bs=%d '
                     % (file_path, count, bs))
        return True

    def get_remaining_disk_space_in_bytes(self):
        s = os.statvfs(self.FOLDER_PATH)
        return s.f_bavail * s.f_frsize

    def run_once(self):
        import pyauto
        self.pyauto.Logout()
        count = 0
        while (self.get_remaining_disk_space_in_bytes() >
               self.DISK_SPACE_BUFFER):
            # We cannot create the large files in the home directory because
            # they will be removed on logout.
            file_path = os.path.join(self.FOLDER_PATH,
                                     ('big_file_%d.data' % count))
            if not self.fill_available_disk_space(
                (self.get_remaining_disk_space_in_bytes() -
                 self.DISK_SPACE_BUFFER), file_path):
                break
            count += 1

        # Generate a unique user name:
        today = datetime.datetime.today()
        username = ('user-%d-%d-%d-%d' %
                    (today.day, today.hour, today.minute, today.microsecond))
        self.pyauto.Login(username, 'fakepassword')
        login_info = self.pyauto.GetLoginInfo()
        if login_info['is_logged_in']:
            raise error.TestFail('Could log in with new user with amount of '
                                 'space available: %d bytes.' %
                                 self.get_remaining_disk_space_in_bytes())

