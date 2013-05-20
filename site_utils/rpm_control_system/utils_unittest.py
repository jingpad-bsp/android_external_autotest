#!/usr/bin/python
# Copyright (c) 2013 The Chromium OS Authors. All rights reserved.
# Use of this source code is governed by a BSD-style license that can be
# found in the LICENSE file.

import __builtin__
import mox
import os
import unittest
from StringIO import StringIO

import utils


class TestUtils(mox.MoxTestBase):
    """Test utility functions."""


    def test_load_servo_interface_mapping(self):
        """Test servo-interface mapping file can be loaded."""
        self.mox.StubOutWithMock(__builtin__, 'open')
        fake_content = (
                'chromeos1-rack5-host10-servo, chromeos1-poe-switch1, fa42\n'
                'chromeos1-rack5-host11-servo, chromeos1-poe-switch1, fa43\n'
                ', chromeos2-poe-switch8, fa43\n'
                'chromeos2-rack5-host11-servo, chromeos2-poe-switch8, fa44\n')
        fake_file = self.mox.CreateMockAnything()
        fake_file.__enter__().AndReturn(StringIO(fake_content))
        fake_file.__exit__(mox.IgnoreArg(), mox.IgnoreArg(), mox.IgnoreArg())
        open('fake_file.csv').AndReturn(fake_file)
        expect = {'chromeos1-rack5-host10-servo':
                          ('chromeos1-poe-switch1', 'fa42'),
                  'chromeos1-rack5-host11-servo':
                          ('chromeos1-poe-switch1', 'fa43'),
                  'chromeos2-rack5-host11-servo':
                          ('chromeos2-poe-switch8', 'fa44')}
        self.mox.ReplayAll()
        self.assertEqual(
                utils.load_servo_interface_mapping('fake_file.csv'), expect)
        self.mox.VerifyAll()


    def _reload_helper(self, do_reload):
        """Helper class for mapping file reloading tests."""
        self.mox.StubOutWithMock(utils, 'load_servo_interface_mapping')
        self.mox.StubOutWithMock(os.path, 'getmtime')
        check_point = 1369783561.8525634
        if do_reload:
            last_modified = check_point + 10.0
            servo_interface = {'fake_servo': ('fake_switch', 'fake_if')}
            utils.load_servo_interface_mapping('fake_file').AndReturn(
                    servo_interface)
        else:
            last_modified = check_point
        os.path.getmtime(mox.IgnoreArg()).AndReturn(last_modified)
        self.mox.ReplayAll()
        result = utils.reload_servo_interface_mapping_if_necessary(
                check_point, mapping_file='fake_file')
        if do_reload:
            self.assertEqual(result, (last_modified, servo_interface))
        else:
            self.assertIsNone(result)
        self.mox.VerifyAll()


    def test_reload_servo_interface_mapping_necessary(self):
        """Test that mapping file is reloaded when it is modified."""
        self._reload_helper(True)


    def test_reload_servo_interface_mapping_not_necessary(self):
        """Test that mapping file is not reloaded when it is not modified."""
        self._reload_helper(False)


if __name__ == '__main__':
    unittest.main()
