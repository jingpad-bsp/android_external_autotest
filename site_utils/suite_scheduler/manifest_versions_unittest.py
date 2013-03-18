#!/usr/bin/python
#
# Copyright (c) 2012 The Chromium OS Authors. All rights reserved.
# Use of this source code is governed by a BSD-style license that can be
# found in the LICENSE file.

"""Unit tests for site_utils/manifest_versions.py."""

# Turn off "access to protected member of class"
# pylint: disable=W0212

import mox, os, unittest, re

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
        self.mv = manifest_versions.ManifestVersions()


    def testInitialize(self):
        """Ensure we can initialize a ManifestVersions."""
        self.mox.StubOutWithMock(self.mv, '_Clone')
        self.mv._Clone()
        self.mox.ReplayAll()
        self.mv.Initialize()


    def testGlobs(self):
        """Ensure that we expand globs correctly."""
        desired_paths = ['one/path', 'two/path', 'three/path']
        tempdir = self.mv._tempdir.name
        for path in desired_paths:
            os.makedirs(os.path.join(tempdir, path))
        for path in self.mv._ExpandGlobMinusPrefix(tempdir, '*/path'):
            self.assertTrue(path in desired_paths)


    def _ExpectGlob(self, to_return):
        self.mox.StubOutWithMock(self.mv, '_ExpandGlobMinusPrefix')
        self.mv._ExpandGlobMinusPrefix(mox.IgnoreArg(),
                                       mox.IgnoreArg()).AndReturn(to_return)


    def testAnyManifestsSinceRev(self):
        """Ensure we can tell if builds have succeeded since a given rev."""
        rev = 'rev'
        self._ExpectGlob(['some/paths'])
        self.mox.StubOutWithMock(manifest_versions, '_SystemOutput')
        manifest_versions._SystemOutput(
            mox.And(mox.StrContains('log'),
                    mox.StrContains(rev))).MultipleTimes().AndReturn(
                        self._MANIFESTS_STRING)
        self.mox.ReplayAll()
        self.assertTrue(self.mv.AnyManifestsSinceRev(rev))


    def testNoManifestsSinceRev(self):
        """Ensure we can tell if no builds have succeeded since a given rev."""
        rev = 'rev'
        self._ExpectGlob(['some/paths'])
        self.mox.StubOutWithMock(manifest_versions, '_SystemOutput')
        manifest_versions._SystemOutput(
            mox.And(mox.StrContains('log'),
                    mox.StrContains(rev))).MultipleTimes().AndReturn(' ')
        self.mox.ReplayAll()
        self.assertFalse(self.mv.AnyManifestsSinceRev(rev))


    def testNoManifestsPathsSinceRev(self):
        """Ensure we can tell that we have no paths to check for new builds."""
        rev = 'rev'
        self._ExpectGlob([])
        self.mox.ReplayAll()
        self.assertFalse(self.mv.AnyManifestsSinceRev(rev))


    def testManifestsSinceDays(self):
        """Ensure we can get manifests for a board since N days ago."""
        days_ago = 7
        board = 'x86-alex'
        self._ExpectGlob(['some/paths'])
        self.mox.StubOutWithMock(manifest_versions, '_SystemOutput')
        manifest_versions._SystemOutput(
            mox.StrContains('log')).MultipleTimes().AndReturn(
                self._MANIFESTS_STRING)
        self.mox.ReplayAll()
        br_man = self.mv.ManifestsSinceDays(days_ago, board)
        for pair in br_man.keys():
            self.assertTrue(pair, self._BRANCHES)
        for manifest_list in br_man.itervalues():
            self.assertTrue(manifest_list)
        self.assertEquals(br_man[('release', '20')][-1], '2057.0.10')


    def testNoManifestsSinceDays(self):
        """Ensure we can deal with no manifests since N days ago."""
        days_ago = 7
        board = 'x86-alex'
        self._ExpectGlob(['some/paths'])
        self.mox.StubOutWithMock(manifest_versions, '_SystemOutput')
        manifest_versions._SystemOutput(mox.StrContains('log')).AndReturn([])
        self.mox.ReplayAll()
        br_man = self.mv.ManifestsSinceDays(days_ago, board)
        self.assertEquals(br_man, {})


    def testNoManifestsPathsSinceDays(self):
        """Ensure we can deal with finding no paths to pass to'git log'."""
        days_ago = 7
        board = 'x86-alex'
        self._ExpectGlob([])
        self.mox.ReplayAll()
        br_man = self.mv.ManifestsSinceDays(days_ago, board)
        self.assertEquals(br_man, {})


    def testManifestsSinceDaysExplodes(self):
        """Ensure we handle failures in querying manifests."""
        days_ago = 7
        board = 'x86-alex'
        self._ExpectGlob(['some/paths'])
        self.mox.StubOutWithMock(manifest_versions, '_SystemOutput')
        manifest_versions._SystemOutput(mox.StrContains('log')).AndRaise(
            manifest_versions.QueryException())
        self.mox.ReplayAll()
        self.assertRaises(manifest_versions.QueryException,
                          self.mv.ManifestsSinceDays, days_ago, board)


    _BOARD_MANIFESTS = {
        'lumpy': [
            'lumpy-factory',
            'lumpy-release',
            'lumpy-pgo-release',
        ],
        'x86-alex': [
            'x86-alex-release',
            'x86-alex-release-group',
        ],
        'link': [
            'link-depthcharge-firmware',
        ],
    }


    def testBoardManifestRePattern(self):
        """Ensure we can parse the names of builds that are produced."""
        for board, builder_names in self._BOARD_MANIFESTS.items():
            rgx = re.compile(
                manifest_versions.ManifestVersions._BOARD_MANIFEST_RE_PATTERN %\
                    board)
            for builder_name in builder_names:
                manifest = 'build-name/%s/pass/25/1234.0.0.xml' % builder_name
                self.assertTrue(rgx.match(manifest), msg=builder_name)


if __name__ == '__main__':
    unittest.main()
