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


class ConvertToKwargsOnlyTest(unittest.TestCase):
    """Unit tests for _convert_to_kwargs_only()."""

    # pylint: disable=unused-argument,missing-docstring

    def test_no_kwargs_in_spec(self):
        """Test with function without kwargs."""
        def func(a, b):
            pass
        got = rpc_utils._convert_to_kwargs_only(func, (1, 2), {})
        self.assertEquals(got, {'a': 1, 'b': 2})

    def test_pass_by_keyword(self):
        """Test passing required args by keyword."""
        def func(a, b):
            pass
        got = rpc_utils._convert_to_kwargs_only(func, (), {'a': 1, 'b': 2})
        self.assertEquals(got, {'a': 1, 'b': 2})

    def test_with_kwargs(self):
        """Test with custom keyword arg."""
        def func(a, b, **kwargs):
            pass
        got = rpc_utils._convert_to_kwargs_only(func, (1, 2), {'c': 3})
        self.assertEquals(got, {'a': 1, 'b': 2, 'c': 3})

    def test_with_kwargs_pass_by_keyword(self):
        """Test passing required parameter by keyword."""
        def func(a, b, **kwargs):
            pass
        got = rpc_utils._convert_to_kwargs_only(func, (1,), {'b': 2, 'c': 3})
        self.assertEquals(got, {'a': 1, 'b': 2, 'c': 3})

    def test_empty_kwargs(self):
        """Test without passing kwargs."""
        def func(a, b, **kwargs):
            pass
        got = rpc_utils._convert_to_kwargs_only(func, (1, 2), {})
        self.assertEquals(got, {'a': 1, 'b': 2})

    def test_with_varargs(self):
        """Test against vararg function."""
        def func(a, b, *args):
            pass
        got = rpc_utils._convert_to_kwargs_only(func, (1, 2, 3), {})
        self.assertEquals(got, {'a': 1, 'b': 2, 'args': (3,)})


if __name__ == '__main__':
    unittest.main()
