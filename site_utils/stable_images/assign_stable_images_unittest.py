# Copyright 2016 The Chromium OS Authors. All rights reserved.
# Use of this source code is governed by a BSD-style license that can be
# found in the LICENSE file.

import json
import os
import sys
import unittest

import common
from autotest_lib.site_utils import assign_stable_images


# _OMAHA_TEST_DATA - File with JSON data to be used as test input to
#   `_make_omaha_versions()`.  In the file, the various items in the
#   `omaha_data` list are selected to capture various specific test
#   cases:
#     + Board with no "beta" channel.
#     + Board with "beta" and another channel.
#     + Board with only a "beta" channel.
#     + Obsolete board with "is_active" set to false.
# The JSON content of the file is a subset of an actual
# `omaha_status.json` file copied when this unit test was new.
#
# _EXPECTED_OMAHA_VERSIONS - The expected output produced by
#   _STUB_OMAHA_DATA.
#
_OMAHA_TEST_DATA = 'test_omaha_status.json'

_EXPECTED_OMAHA_VERSIONS = {'arkham': 'R53-8530.71.1',
                            'auron-paine': 'R54-8743.44.0',
                            'zako-freon': 'R41-6680.52.0'}

_DEFAULT_BOARD = assign_stable_images._DEFAULT_BOARD


class OmahaDataTests(unittest.TestCase):
    """
    Tests for the `_make_omaha_versions()` function.
    """

    def test_make_omaha_versions(self):
        """
        Test `_make_omaha_versions()` against one simple input.

        This is a trivial sanity test that confirms that a single
        hard-coded input returns a correct hard-coded output.
        """
        module_dir = os.path.dirname(sys.modules[__name__].__file__)
        data_file_path = os.path.join(module_dir, _OMAHA_TEST_DATA)
        omaha_versions = assign_stable_images._make_omaha_versions(
                json.load(open(data_file_path, 'r')))
        self.assertEqual(omaha_versions, _EXPECTED_OMAHA_VERSIONS)


class UpgradeVersionsTests(unittest.TestCase):
    """
    Tests for the `_get_upgrade_versions()` function.
    """

    # _VERSIONS - a list of sample version strings such as may be used
    #   for Chrome OS, sorted from oldest to newest.  These are used to
    #   construct test data in multiple test cases, below.
    _VERSIONS = ['R1-1.0.0', 'R1-1.1.0', 'R2-4.0.0']

    def test_board_conversions(self):
        """
        Test proper mapping of names from the AFE to Omaha.

        Board names in Omaha don't have '_' characters; when an AFE
        board contains '_' characters, they must be converted to '-'.

        Assert that for various forms of name in the AFE mapping, the
        converted name is the one looked up in the Omaha mapping.
        """
        board_equivalents = [
            ('a-b', 'a-b'), ('c_d', 'c-d'),
            ('e_f-g', 'e-f-g'), ('hi', 'hi')]
        afe_versions = {
            _DEFAULT_BOARD: self._VERSIONS[0]
        }
        omaha_versions = {}
        expected = {}
        boards = set()
        for afe_board, omaha_board in board_equivalents:
            boards.add(afe_board)
            afe_versions[afe_board] = self._VERSIONS[1]
            omaha_versions[omaha_board] = self._VERSIONS[2]
            expected[afe_board] = self._VERSIONS[2]
        upgrades, _ = assign_stable_images._get_upgrade_versions(
                afe_versions, omaha_versions, boards)
        self.assertEqual(upgrades, expected)

    def test_afe_default(self):
        """
        Test that the AFE default board mapping is honored.

        If a board isn't present in the AFE dictionary, the mapping
        for `_DEFAULT_BOARD` should be used.

        Primary assertions:
          * When a board is present in the AFE mapping, its version
            mapping is used.
          * When a board is not present in the AFE mapping, the default
            version mapping is used.

        Secondarily, assert that when a mapping is absent from Omaha,
        the AFE mapping is left unchanged.
        """
        afe_versions = {
            _DEFAULT_BOARD: self._VERSIONS[0],
            'a': self._VERSIONS[1]
        }
        boards = set(['a', 'b'])
        expected = {
            'a': self._VERSIONS[1],
            'b': self._VERSIONS[0]
        }
        upgrades, _ = assign_stable_images._get_upgrade_versions(
                afe_versions, {}, boards)
        self.assertEqual(upgrades, expected)

    def test_omaha_upgrade(self):
        """
        Test that upgrades from Omaha are detected.

        Primary assertion:
          * If a board is found in Omaha, and the version in Omaha is
            newer than the AFE version, the Omaha version is the one
            used.

        Secondarily, asserts that version comparisons between various
        specific version strings are all correct.
        """
        boards = set(['a'])
        for i in range(0, len(self._VERSIONS) - 1):
            afe_versions = {_DEFAULT_BOARD: self._VERSIONS[i]}
            for j in range(i+1, len(self._VERSIONS)):
                omaha_versions = {b: self._VERSIONS[j] for b in boards}
                upgrades, _ = assign_stable_images._get_upgrade_versions(
                        afe_versions, omaha_versions, boards)
                self.assertEqual(upgrades, omaha_versions)

    def test_no_upgrade(self):
        """
        Test that if Omaha is behind the AFE, it is ignored.

        Primary assertion:
          * If a board is found in Omaha, and the version in Omaha is
            older than the AFE version, the AFE version is the one used.

        Secondarily, asserts that version comparisons between various
        specific version strings are all correct.
        """
        boards = set(['a'])
        for i in range(1, len(self._VERSIONS)):
            afe_versions = {_DEFAULT_BOARD: self._VERSIONS[i]}
            expected = {b: self._VERSIONS[i] for b in boards}
            for j in range(0, i):
                omaha_versions = {b: self._VERSIONS[j] for b in boards}
                upgrades, _ = assign_stable_images._get_upgrade_versions(
                        afe_versions, omaha_versions, boards)
                self.assertEqual(upgrades, expected)

    def test_ignore_unused_boards(self):
        """
        Test that unlisted boards are ignored.

        Assert that boards present in the AFE or Omaha mappings aren't
        included in the return mappings when they aren't in the passed
        in set of boards.
        """
        unused_boards = set(['a', 'b'])
        used_boards = set(['c', 'd'])
        afe_versions = {b: self._VERSIONS[0] for b in unused_boards}
        afe_versions[_DEFAULT_BOARD] = self._VERSIONS[1]
        expected = {b: self._VERSIONS[1] for b in used_boards}
        omaha_versions = expected.copy()
        omaha_versions.update(
                {b: self._VERSIONS[0] for b in unused_boards})
        upgrades, _ = assign_stable_images._get_upgrade_versions(
                afe_versions, omaha_versions, used_boards)
        self.assertEqual(upgrades, expected)

    def test_default_unchanged(self):
        """
        Test correct handling when the default build is unchanged.

        Assert that if in Omaha, one board in a set of three upgrades
        from the AFE default, that the returned default board mapping is
        the original default in the AFE.
        """
        boards = set(['a', 'b', 'c'])
        afe_versions = {_DEFAULT_BOARD: self._VERSIONS[0]}
        omaha_versions = {b: self._VERSIONS[0] for b in boards}
        omaha_versions['c'] = self._VERSIONS[1]
        _, new_default = assign_stable_images._get_upgrade_versions(
                afe_versions, omaha_versions, boards)
        self.assertEqual(new_default, self._VERSIONS[0])

    def test_default_upgrade(self):
        """
        Test correct handling when the default build must change.

        Assert that if in Omaha, two boards in a set of three upgrade
        from the AFE default, that the returned default board mapping is
        the new build in Omaha.
        """
        boards = set(['a', 'b', 'c'])
        afe_versions = {_DEFAULT_BOARD: self._VERSIONS[0]}
        omaha_versions = {b: self._VERSIONS[1] for b in boards}
        omaha_versions['c'] = self._VERSIONS[0]
        _, new_default = assign_stable_images._get_upgrade_versions(
                afe_versions, omaha_versions, boards)
        self.assertEqual(new_default, self._VERSIONS[1])


if __name__ == '__main__':
    unittest.main()
