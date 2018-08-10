# Copyright 2018 The Chromium OS Authors. All rights reserved.
# Use of this source code is governed by a BSD-style license that can be
# found in the LICENSE file.

import logging
import os
import sys

from dbus.mainloop.glib import DBusGMainLoop

from autotest_lib.client.bin import test
from autotest_lib.client.common_lib import error
from autotest_lib.client.common_lib import utils
from autotest_lib.client.common_lib.cros import smbprovider

class enterprise_SmbProviderDaemon(test.test):
    """
    Test for SmbProvider Daemon.

    """

    version = 1

    WORKGROUP = ''
    USERNAME = ''
    PASSWORD = ''

    def setup(self):
        """
        Compiles protobufs for error type and input/output parameters.

        """

        os.chdir(self.srcdir)
        utils.make('OUT_DIR=.')

    def initialize(self):
        """
        Initializes the D-Bus loop and creates Python wrapper.

        """

        bus_loop = DBusGMainLoop(set_as_default=True)
        self._smbprovider = smbprovider.SmbProvider(bus_loop, self.srcdir)

        # Append path for directory_entry_pb2 imports.
        sys.path.append(self.srcdir)

    def run_once(self, mount_path):
        """
        Runs smbproviderd D-Bus commands.

        @param mount_path: Address of the SMB share.
        """

        self.sanity_test(mount_path)

    def _generate_random_id(self, size):
        """
        Generates a random string of size N.

        @param size: Size of the generated string.

        @return: Returns a random alphanumeric string of size N.

        """

        import string
        import random

        return ''.join(random.choice(string.ascii_uppercase +
                                string.digits) for i in range(size))

    def sanity_test(self, mount_path):
        """
        Sanity test that runs through all filesystem operations
        on the SmbProvider Daemon.

        @param mount_path: Address of the SMB share.

        """

        mount_id = self._check_mount(mount_path)

        # Generate random directory
        rand_dir_id = self._generate_random_id(10)

        test_dir = '/autotest_' + rand_dir_id + '/'
        test_file = test_dir + '1.txt'

        self._check_create_directory(mount_id, test_dir, False)
        self._check_create_file(mount_id, test_file)

        # Open file with Read-Only priviledges.
        file_id = self._check_open_file(mount_id, test_file, False)
        self._check_close_file(mount_id, file_id)

        # Open file with Writeable priviledges.
        file_id = self._check_open_file(mount_id, test_file, True)
        self._check_close_file(mount_id, file_id)

        self._check_delete_entry(mount_id, test_file, False)
        self._check_delete_entry(mount_id, test_dir, False)

        self._check_unmount(mount_id)

    def _check_mount(self, mount_path):
        """
        Checks that mount is working.

        @param mount_path: Address of the SMB share.

        @return mount_id: Unique identifier of the mount.

        """

        from directory_entry_pb2 import ERROR_OK

        error, mount_id = self._smbprovider.mount(mount_path,
                                                  self.WORKGROUP,
                                                  self.USERNAME,
                                                  self.PASSWORD)

        if mount_id < 0 :
            error.TestFail('Unexpected failure with mount id.')

        self._check_result('Mount', error)
        return mount_id

    def _check_unmount(self, mount_id):
        """
        Checks that unmount is working.

        @param mount_id: Unique identifier of the mount.

        """

        error = self._smbprovider.unmount(mount_id)

        self._check_result('Unmount', error)

    def _check_create_file(self, mount_id, file_path):
        """
        Checks that create file is working.

        @param mount_id: Unique identifier of the mount.
        @param file_path: Path of where the new file will be created.

        """

        error = self._smbprovider.create_file(mount_id, file_path)

        self._check_result('Create File', error)

    def _check_open_file(self, mount_id, file_path, writeable):
        """
        Checks that open file is working.

        @param mount_id: Unique identifier of the mount.
        @param file_path: Path of where the file is located.
        @param writeable: Boolean to indicated whether the file should
                be opened with write access.

        """

        error, file_id = self._smbprovider.open_file(mount_id,
                                                     file_path,
                                                     writeable)

        if not file_id:
            error.TestFail('Unexpected file id failure.')

        self._check_result('Open File', error)

        return file_id

    def _check_close_file(self, mount_id, file_id):
        """
        Checks that close file is working.

        @param mount_id: Unique identifier of the mount.
        @param file_id: Unique identifier of the file.

        """

        error = self._smbprovider.close_file(mount_id, file_id)

        self._check_result('Close File', error)

    def _check_create_directory(self, mount_id,
                                      directory_path,
                                      recursive):
        """
        Checks that create directory is working.

        @param mount_id: Unique identifier of the mount.
        @param directory_path: Path for the test directory.
        @param recursive: Boolean to indicate whether directories should be
                created recursively.

        """

        error = self._smbprovider.create_directory(mount_id,
                                                   directory_path,
                                                   recursive)

        self._check_result('Create Directory', error)

    def _check_delete_entry(self, mount_id, entry_path, recursive):
        """
        Checks that delete an entry works.

        @param mount_id: Unique identifier of the mount.
        @param entry_path: Path to the file/directory to delete.
        @param recursive: Boolean to indicate recursive deletes.

        """

        error = self._smbprovider.delete_entry(mount_id,
                                               entry_path,
                                               recursive)

        self._check_result('Delete Entry', error)

    def _check_result(self, method_name, result, expected=None):
        """
        Helper to check error codes and throw on mismatch.

        Checks whether the returned ErrorType from a D-Bus call to smbproviderd
        matches the expected ErrorType. In case of a mismatch, throws a
        TestError.

        @param method_name: Name of the D-Bus method that was called.
        @param result: ErrorType returned from the D-Bus call.
        @param expected: Expected ErrorType. Default: ErrorType.ERROR_OK.

        """

        from directory_entry_pb2 import ErrorType
        from directory_entry_pb2 import ERROR_OK

        if not expected:
            expected = ERROR_OK

        if result != expected:
            logging.error('Failed to run %s', method_name)
            raise error.TestFail(
                    '%s failed with error %s (%s), expected %s (%s)' % (
                    method_name, result, ErrorType.Name(result), expected,
                    ErrorType.Name(expected)))
