#!/usr/bin/python
#
# Copyright (c) 2012 The Chromium OS Authors. All rights reserved.
# Use of this source code is governed by a BSD-style license that can be
# found in the LICENSE file.

"""Unit tests for site_utils/board_enumerator.py."""

import logging
import mox
import unittest

import board_enumerator

from autotest_lib.server import frontend


class PlatformEnumeratorTest(mox.MoxTestBase):
    """Unit tests for PlatformEnumerator."""


    def setUp(self):
        super(PlatformEnumeratorTest, self).setUp()
        self.afe = self.mox.CreateMock(frontend.AFE)
        self.enumerator = board_enumerator.PlatformEnumerator(afe=self.afe)
        self.prefix = self.enumerator._LABEL_PREFIX


    def _CreateMockLabel(self, name):
        """Creates a mock frontend.Label, with the given name."""
        mock = self.mox.CreateMock(frontend.Label)
        mock.name = name
        return mock


    def testEnumerateBoards(self):
        """Test successful platform enumeration."""
        labels = ['platform1', 'platform2', 'platform3']
        self.afe.get_labels(name__startswith=self.prefix).AndReturn(
            map(lambda p: self._CreateMockLabel(self.prefix+p), labels))
        self.mox.ReplayAll()
        self.assertEquals(labels, self.enumerator.Enumerate())


    def testEnumerateNoPlatforms(self):
        """Test successful platform enumeration, but there are no platforms."""
        self.afe.get_labels(name__startswith=self.prefix).AndReturn([])
        self.mox.ReplayAll()
        self.assertRaises(board_enumerator.NoPlatformException,
                          self.enumerator.Enumerate)


    def testEnumeratePlatformsExplodes(self):
        """Listing platforms raises an exception from the AFE."""
        self.afe.get_labels(name__startswith=self.prefix).AndRaise(Exception())
        self.mox.ReplayAll()
        self.assertRaises(board_enumerator.EnumerateException,
                          self.enumerator.Enumerate)


if __name__ == '__main__':
    unittest.main()
