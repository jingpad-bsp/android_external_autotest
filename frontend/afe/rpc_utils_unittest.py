#!/usr/bin/python
#
# Copyright (c) 2016 The Chromium OS Authors. All rights reserved.
# Use of this source code is governed by a BSD-style license that can be
# found in the LICENSE file.

"""Unit tests for frontend/afe/rpc_utils.py."""


import unittest

import common
from autotest_lib.client.common_lib import control_data
from autotest_lib.frontend import setup_django_environment
from autotest_lib.frontend.afe import frontend_test_utils
from autotest_lib.frontend.afe import rpc_utils


class RpcUtilsTest(unittest.TestCase,
                   frontend_test_utils.FrontendTestMixin):
    """Unit tests for functions in rpc_utils.py."""
    def setUp(self):
        self._frontend_common_setup()


    def tearDown(self):
        self._frontend_common_teardown()


    def testCheckIsServer(self):
        """Ensure that test type check is correct."""
        self.assertFalse(rpc_utils._check_is_server_test(None))
        self.assertFalse(rpc_utils._check_is_server_test(
            control_data.CONTROL_TYPE.CLIENT))
        self.assertFalse(rpc_utils._check_is_server_test('Client'))
        self.assertTrue(rpc_utils._check_is_server_test(
            control_data.CONTROL_TYPE.SERVER))
        self.assertTrue(rpc_utils._check_is_server_test('Server'))
        self.assertFalse(rpc_utils._check_is_server_test('InvalidType'))


if __name__ == '__main__':
    unittest.main()
