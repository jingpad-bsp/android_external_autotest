#!/usr/bin/python
# Copyright (c) 2013 The Chromium OS Authors. All rights reserved.
# Use of this source code is governed by a BSD-style license that can be
# found in the LICENSE file.

import mox
import unittest

import common

import autoupdater


class TestAutoUpdater(mox.MoxTestBase):
    """Test autoupdater module."""


    def testParseBuildFromUpdateUrlwithUpdate(self):
        """Test that we properly parse the build from an update_url."""
        update_url = ('http://172.22.50.205:8082/update/lumpy-release/'
                      'R27-3837.0.0')
        expected_value = 'lumpy-release/R27-3837.0.0'
        self.assertEqual(autoupdater.url_to_image_name(update_url),
                         expected_value)


    def testCheckVersion(self):
        """Test version check methods work for any build.

        Test two methods used to check version, check_version and
        check_version_to_confirm_install, work for both official build and
        non-official builds.

        """
        update_url = ('http://172.22.50.205:8082/update/lumpy-release/'
                      'R27-3880.0.0')
        updater = autoupdater.ChromiumOSUpdater(update_url)

        self.mox.StubOutWithMock(updater, 'get_build_id')
        updater.get_build_id().MultipleTimes().AndReturn('3880.0.0-rc1')
        self.mox.ReplayAll()

        updater.update_version = '3880.0.0-rc1'
        self.assertTrue(updater.check_version())

        updater.update_version = '3880.0.0-rc10'
        self.assertFalse(updater.check_version())

        updater.update_version = '3880.0.0-rc1'
        self.assertTrue(updater.check_version_to_confirm_install())

        updater.update_version = '3880.0.0'
        self.assertFalse(updater.check_version_to_confirm_install())

        self.mox.UnsetStubs()
        self.mox.StubOutWithMock(updater, 'get_build_id')
        updater.get_build_id().MultipleTimes().AndReturn(
                                                '1234.0.2013_03_21_1340')
        self.mox.ReplayAll()

        updater.update_version = '1234.0.0'
        self.assertFalse(updater.check_version())

        updater.update_version = '3333.0.0'
        self.assertFalse(updater.check_version())

        updater.update_version = '1234.0.0'
        self.assertTrue(updater.check_version_to_confirm_install())

        updater.update_version = '3333.0.0'
        self.assertFalse(updater.check_version_to_confirm_install())


if __name__ == '__main__':
  unittest.main()
