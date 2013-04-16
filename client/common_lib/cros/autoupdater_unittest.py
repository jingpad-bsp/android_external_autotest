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


    def testCheckVersion_1(self):
        """Test version check methods work for any build.

        Test two methods used to check version, check_version and
        check_version_to_confirm_install, for:
        1. trybot paladin build.
        update version: trybot-lumpy-paladin/R27-3837.0.0-b123
        booted version: 3837.0.2013_03_21_1340

        """
        update_url = ('http://172.22.50.205:8082/update/trybot-lumpy-paladin/'
                      'R27-1111.0.0-b123')
        updater = autoupdater.ChromiumOSUpdater(update_url)

        self.mox.UnsetStubs()
        self.mox.StubOutWithMock(updater, 'get_build_id')
        updater.get_build_id().MultipleTimes().AndReturn(
                                                    '1111.0.2013_03_21_1340')
        self.mox.ReplayAll()

        self.assertFalse(updater.check_version())
        self.assertTrue(updater.check_version_to_confirm_install())

        self.mox.UnsetStubs()
        self.mox.StubOutWithMock(updater, 'get_build_id')
        updater.get_build_id().MultipleTimes().AndReturn('1111.0.0-rc1')
        self.mox.ReplayAll()

        self.assertFalse(updater.check_version())
        self.assertFalse(updater.check_version_to_confirm_install())

        self.mox.UnsetStubs()
        self.mox.StubOutWithMock(updater, 'get_build_id')
        updater.get_build_id().MultipleTimes().AndReturn('1111.0.0')
        self.mox.ReplayAll()

        self.assertFalse(updater.check_version())
        self.assertFalse(updater.check_version_to_confirm_install())

    def testCheckVersion_2(self):
        """Test version check methods work for any build.

        Test two methods used to check version, check_version and
        check_version_to_confirm_install, for:
        2. trybot release build.
        update version: trybot-lumpy-release/R27-3837.0.0-b456
        booted version: 3837.0.0

        """
        update_url = ('http://172.22.50.205:8082/update/trybot-lumpy-release/'
                      'R27-2222.0.0-b456')
        updater = autoupdater.ChromiumOSUpdater(update_url)

        self.mox.UnsetStubs()
        self.mox.StubOutWithMock(updater, 'get_build_id')
        updater.get_build_id().MultipleTimes().AndReturn(
                                                    '2222.0.2013_03_21_1340')
        self.mox.ReplayAll()

        self.assertFalse(updater.check_version())
        self.assertFalse(updater.check_version_to_confirm_install())

        self.mox.UnsetStubs()
        self.mox.StubOutWithMock(updater, 'get_build_id')
        updater.get_build_id().MultipleTimes().AndReturn('2222.0.0-rc1')
        self.mox.ReplayAll()

        self.assertFalse(updater.check_version())
        self.assertFalse(updater.check_version_to_confirm_install())

        self.mox.UnsetStubs()
        self.mox.StubOutWithMock(updater, 'get_build_id')
        updater.get_build_id().MultipleTimes().AndReturn('2222.0.0')
        self.mox.ReplayAll()

        self.assertFalse(updater.check_version())
        self.assertTrue(updater.check_version_to_confirm_install())


    def testCheckVersion_3(self):
        """Test version check methods work for any build.

        Test two methods used to check version, check_version and
        check_version_to_confirm_install, for:
        3. buildbot official release build.
        update version: lumpy-release/R27-3837.0.0
        booted version: 3837.0.0

        """
        update_url = ('http://172.22.50.205:8082/update/lumpy-release/'
                      'R27-3333.0.0')
        updater = autoupdater.ChromiumOSUpdater(update_url)

        self.mox.UnsetStubs()
        self.mox.StubOutWithMock(updater, 'get_build_id')
        updater.get_build_id().MultipleTimes().AndReturn(
                                                    '3333.0.2013_03_21_1340')
        self.mox.ReplayAll()

        self.assertFalse(updater.check_version())
        self.assertFalse(updater.check_version_to_confirm_install())

        self.mox.UnsetStubs()
        self.mox.StubOutWithMock(updater, 'get_build_id')
        updater.get_build_id().MultipleTimes().AndReturn('3333.0.0-rc1')
        self.mox.ReplayAll()

        self.assertFalse(updater.check_version())
        self.assertFalse(updater.check_version_to_confirm_install())

        self.mox.UnsetStubs()
        self.mox.StubOutWithMock(updater, 'get_build_id')
        updater.get_build_id().MultipleTimes().AndReturn('3333.0.0')
        self.mox.ReplayAll()

        self.assertTrue(updater.check_version())
        self.assertTrue(updater.check_version_to_confirm_install())


    def testCheckVersion_4(self):
        """Test version check methods work for any build.

        Test two methods used to check version, check_version and
        check_version_to_confirm_install, for:
        4. non-official paladin rc build.
        update version: lumpy-paladin/R27-3837.0.0-rc7
        booted version: 3837.0.0-rc7

        """
        update_url = ('http://172.22.50.205:8082/update/lumpy-paladin/'
                      'R27-4444.0.0-rc7')
        updater = autoupdater.ChromiumOSUpdater(update_url)

        self.mox.UnsetStubs()
        self.mox.StubOutWithMock(updater, 'get_build_id')
        updater.get_build_id().MultipleTimes().AndReturn(
                                                    '4444.0.2013_03_21_1340')
        self.mox.ReplayAll()

        self.assertFalse(updater.check_version())
        self.assertFalse(updater.check_version_to_confirm_install())

        self.mox.UnsetStubs()
        self.mox.StubOutWithMock(updater, 'get_build_id')
        updater.get_build_id().MultipleTimes().AndReturn('4444.0.0-rc7')
        self.mox.ReplayAll()

        self.assertTrue(updater.check_version())
        self.assertTrue(updater.check_version_to_confirm_install())

        self.mox.UnsetStubs()
        self.mox.StubOutWithMock(updater, 'get_build_id')
        updater.get_build_id().MultipleTimes().AndReturn('4444.0.0')
        self.mox.ReplayAll()

        self.assertFalse(updater.check_version())
        self.assertFalse(updater.check_version_to_confirm_install())


    def testCheckVersion_5(self):
        """Test version check methods work for any build.

        Test two methods used to check version, check_version and
        check_version_to_confirm_install, for:
        5. chrome-perf build.
        update version: lumpy-chrome-perf/R28-3837.0.0-b2996
        booted version: 3837.0.0

        """
        update_url = ('http://172.22.50.205:8082/update/lumpy-chrome-perf/'
                      'R28-4444.0.0-b2996')
        updater = autoupdater.ChromiumOSUpdater(update_url)

        self.mox.UnsetStubs()
        self.mox.StubOutWithMock(updater, 'get_build_id')
        updater.get_build_id().MultipleTimes().AndReturn(
                                                    '4444.0.2013_03_21_1340')
        self.mox.ReplayAll()

        self.assertFalse(updater.check_version())
        self.assertFalse(updater.check_version_to_confirm_install())

        self.mox.UnsetStubs()
        self.mox.StubOutWithMock(updater, 'get_build_id')
        updater.get_build_id().MultipleTimes().AndReturn('4444.0.0-rc7')
        self.mox.ReplayAll()

        self.assertFalse(updater.check_version())
        self.assertFalse(updater.check_version_to_confirm_install())

        self.mox.UnsetStubs()
        self.mox.StubOutWithMock(updater, 'get_build_id')
        updater.get_build_id().MultipleTimes().AndReturn('4444.0.0')
        self.mox.ReplayAll()

        self.assertFalse(updater.check_version())
        self.assertTrue(updater.check_version_to_confirm_install())


    def testUpdateStateful(self):
        """Tests that we call the stateful update script with the correct args.
        """
        self.mox.StubOutWithMock(autoupdater.ChromiumOSUpdater, '_run')
        update_url = ('http://172.22.50.205:8082/update/lumpy-chrome-perf/'
                      'R28-4444.0.0-b2996')
        static_update_url = ('http://172.22.50.205:8082/static/archive/'
                             'lumpy-chrome-perf/R28-4444.0.0-b2996')

        # Test with clobber=False.
        autoupdater.ChromiumOSUpdater._run(
                mox.And(
                        mox.StrContains(autoupdater.REMOTE_STATEUL_UPDATE_PATH),
                        mox.StrContains(static_update_url),
                        mox.Not(mox.StrContains('--stateful_change=clean'))),
                timeout=600)

        self.mox.ReplayAll()
        updater = autoupdater.ChromiumOSUpdater(update_url)
        updater.update_stateful(clobber=False)
        self.mox.VerifyAll()

        # Test with clobber=True.
        self.mox.ResetAll()
        autoupdater.ChromiumOSUpdater._run(
                mox.And(
                        mox.StrContains(autoupdater.REMOTE_STATEUL_UPDATE_PATH),
                        mox.StrContains(static_update_url),
                        mox.StrContains('--stateful_change=clean')),
                timeout=600)
        self.mox.ReplayAll()
        updater = autoupdater.ChromiumOSUpdater(update_url)
        updater.update_stateful(clobber=True)
        self.mox.VerifyAll()


if __name__ == '__main__':
  unittest.main()
