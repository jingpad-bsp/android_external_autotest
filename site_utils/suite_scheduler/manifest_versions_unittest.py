#!/usr/bin/python
#
# Copyright (c) 2012 The Chromium OS Authors. All rights reserved.
# Use of this source code is governed by a BSD-style license that can be
# found in the LICENSE file.

"""Unit tests for site_utils/manifest_versions.py."""

import logging, mox, unittest

from autotest_lib.client.common_lib import utils
import manifest_versions


class ManifestVersionsTest(mox.MoxTestBase):
    """Unit tests for ManifestVersions.

    @var _BRANCHES: canned branches that should parse out of the below.
    @var _MANIFESTS_STRING: canned (string) list of manifest file paths.
    """

    _BRANCHES = [('release', '18'), ('release', '19'), ('release', '20'),
                 ('factory', '20'), ('firmware', '20')]
    _MANIFESTS_STRING = """
build-name/x86-alex-release-group/pass/20/2057.0.9.xml


build-name/x86-alex-release-group/pass/20/2057.0.10.xml


build-name/x86-alex-release-group/pass/20/2054.0.0.xml


build-name/x86-alex-release/pass/18/1660.103.0.xml


build-name/x86-alex-release-group/pass/20/2051.0.0.xml


build-name/x86-alex-firmware/pass/20/2048.1.1.xml


build-name/x86-alex-release/pass/19/2046.3.0.xml


build-name/x86-alex-release-group/pass/20/2050.0.0.xml


build-name/x86-alex-release-group/pass/20/2048.0.0.xml


build-name/x86-alex-factory/pass/20/2048.1.0.xml
"""


    def setUp(self):
        super(ManifestVersionsTest, self).setUp()
        self.manifest_versions = manifest_versions.ManifestVersions()


    def testInitialize(self):
        """Ensure we can initialize a ManifestVersions."""
        self.mox.StubOutWithMock(self.manifest_versions, '_Clone')
        self.manifest_versions._Clone()
        self.mox.ReplayAll()
        self.manifest_versions.Initialize()


    def testManifestsSince(self):
        """Ensure we can get manifests for a board since N days ago."""
        days_ago = 7
        board = 'x86-alex'
        self.mox.StubOutWithMock(utils, 'system_output')
        utils.system_output(mox.StrContains('git log')).AndReturn(
            self._MANIFESTS_STRING)
        self.mox.ReplayAll()
        br_man = self.manifest_versions.ManifestsSince(days_ago, board)
        for pair in br_man.keys():
            self.assertTrue(pair, self._BRANCHES)
        for manifest_list in br_man.itervalues():
            self.assertTrue(manifest_list)
        self.assertEquals(br_man[('release', '20')][-1], '2057.0.10')


    def testManifestsSinceExplodes(self):
        """Ensure we handle failures in querying manifests."""
        days_ago = 7
        board = 'x86-alex'
        self.mox.StubOutWithMock(utils, 'system_output')
        utils.system_output(mox.StrContains('git log')).AndRaise(
            manifest_versions.QueryException())
        self.mox.ReplayAll()
        self.assertRaises(manifest_versions.QueryException,
                          self.manifest_versions.ManifestsSince,
                          days_ago, board)


if __name__ == '__main__':
    unittest.main()
