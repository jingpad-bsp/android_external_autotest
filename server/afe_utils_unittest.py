#!/usr/bin/python
# Copyright 2016 The Chromium OS Authors. All rights reserved.
# Use of this source code is governed by a BSD-style license that can be
# found in the LICENSE file.

import unittest

import common
from autotest_lib.server import afe_utils
from autotest_lib.server import site_utils
from autotest_lib.server.cros import provision
from autotest_lib.server.cros.dynamic_suite import constants


class MockHost(object):
    """
    Object to represent host used to test afe_util.py methods.
    """

    def __init__(self, labels=[]):
      """
      Setup the self._afe_host attribute since that's what we're mostly using.
      """
      self._afe_host = site_utils.EmptyAFEHost()
      self._afe_host.labels = labels


class AfeUtilsUnittest(unittest.TestCase):
    """
    Test functions in afe_utils.py.
    """

    def testGetLabels(self):
        """
        Test method get_labels returns expected labels.
        """
        prefix = 'prefix'
        expected_labels = [prefix + ':' + str(i) for i in range(5)]
        all_labels = []
        all_labels += expected_labels
        all_labels += [str(i) for i in range(6, 9)]
        host = MockHost(labels=all_labels)
        got_labels = afe_utils.get_labels(host, prefix)

        self.assertItemsEqual(got_labels, expected_labels)


    def testGetLabelsAll(self):
        """
        Test method get_labels returns all labels.
        """
        prefix = 'prefix'
        prefix_labels = [prefix + ':' + str(i) for i in range(5)]
        all_labels = []
        all_labels += prefix_labels
        all_labels += [str(i) for i in range(6, 9)]
        host = MockHost(labels=all_labels)
        got_labels = afe_utils.get_labels(host)

        self.assertItemsEqual(got_labels, all_labels)


    def testGetBuild(self):
      """
      Test method get_build returns expected labels.
      """
      expected_build = '1.2.3.4'
      for label_prefix in [provision.CROS_VERSION_PREFIX,
                           provision.ANDROID_BUILD_VERSION_PREFIX,
                           provision.TESTBED_BUILD_VERSION_PREFIX]:
          build_label = label_prefix + ':' + expected_build
          all_labels = [build_label]
          all_labels += [str(i) for i in range(5)]
          host = MockHost(labels=all_labels)

          got_build = afe_utils.get_build(host)
          self.assertEqual(got_build, expected_build)


    def testGetBoard(self):
      """
      Test method get_board returns expected labels.
      """
      expected_board = 'funky_town'
      board_label = constants.BOARD_PREFIX + expected_board
      all_labels = [board_label]
      all_labels += [str(i) for i in range(5)]
      host = MockHost(labels=all_labels)

      got_board = afe_utils.get_board(host)
      self.assertEqual(got_board, expected_board)


    def testGetBoards(self):
      """
      Test method get_boards returns expected labels.
      """
      expected_boards = ['funky_town', 'jazz_river']
      board_labels = [constants.BOARD_PREFIX + expected_board
                      for expected_board in expected_boards]
      all_labels = board_labels
      all_labels += [str(i) for i in range(5)]
      host = MockHost(labels=all_labels)

      got_boards = afe_utils.get_boards(host)
      self.assertEqual(got_boards, expected_boards)


if __name__ == '__main__':
    unittest.main()

