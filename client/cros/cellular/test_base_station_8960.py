# Copyright (c) 2011 The Chromium OS Authors. All rights reserved.
# Use of this source code is governed by a BSD-style license that can be
# found in the LICENSE file.

import unittest
from base_station_8960 import BaseStation8960


class TestMakeOne(unittest.TestCase):
    """
    Instantiate a base station
    """
    def SetUp(self):
        """
        runs before each test in this class
        """
        pass


    def testMakeOne(self):
        """
        make an 8960 object
        """
        bs=BaseStation8960()
