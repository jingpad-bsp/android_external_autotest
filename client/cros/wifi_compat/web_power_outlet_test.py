# Copyright (c) 2012 The Chromium Authors. All rights reserved.
# Use of this source code is governed by a BSD-style license that can be
# found in the LICENSE file.

import unittest

import web_power_outlet


class WebPowerOutletTest(unittest.TestCase):
    """Test class for the WebPowerOutlet class.

    This test needs to be run against the UI interface.

    This class provides a fast way to test without having to run_remote_test
    because chances are you don't need a ChromeOS device.  You will need to run
    this like:
    $ PYTHONPATH=../../deps/pyauto_dep/test_src/third_party/webdriver/pylib/
      python web_power_outlet_test.py
    """

    def setUp(self):
        # Build the object, feel free to adjust the initialization parameters.
        self.power_outlet = web_power_outlet.WebPowerOutlet(
            '172.22.50.239', 3, 'admin', '1234')

    def test_turning_on(self):
        """Test turning the outlet on."""
        self.power_outlet.turn_on_outlet()
        self.assertTrue(self.power_outlet.get_outlet_state(),
                        msg='The outlet should be on.')

    def test_turning_off(self):
        """Test turning the outlet off."""
        self.power_outlet.turn_off_outlet()
        self.assertFalse(self.power_outlet.get_outlet_state(),
                         msg='The outlet should be off.')

    def test_getting_state(self):
        """Test the state of the outlet can be returned at any time."""
        self.assertNotEqual(self.power_outlet.get_outlet_state(), None,
                            msg='The outlet did not return a state.')


if __name__ == '__main__':
    unittest.main()
