#!/usr/bin/python

__author__ = "gwendal@google.com (Gwendal Grignou)"

import unittest

from autotest_lib.client.bin import utils

class TestUtils(unittest.TestCase):
    """Test utils functions."""


    def test_concat_partition(self):
        self.assertEquals("nvme0n1p3", utils.concat_partition("nvme0n1", 3))
        self.assertEquals("mmcblk1p3", utils.concat_partition("mmcblk1", 3))
        self.assertEquals("sda3", utils.concat_partition("sda", 3))



