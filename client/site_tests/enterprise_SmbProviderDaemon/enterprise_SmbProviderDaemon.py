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

        """

        self._check_mount(mount_path)

    def _check_mount(self, mount_path):
        """
        Checks that mount is working.

        """

        error, mount_id = self._smbprovider.mount(mount_path,
                                                  self.WORKGROUP,
                                                  self.USERNAME,
                                                  self.PASSWORD)
        self._check_result("Mount", error)

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
                    '%s failed with error %s (%s), expected %s (%s)' %
                    method_name, result, ErrorType.Name(result), expected,
                    ErrorType.Name(expected))

