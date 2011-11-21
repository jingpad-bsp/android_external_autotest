#!/usr/bin/python
#
# Copyright (c) 2011 The Chromium OS Authors. All rights reserved.
# Use of this source code is governed by a BSD-style license that can be
# found in the LICENSE file.

"""Unit tests for DevServer class."""

__author__ = 'dalecurtis@google.com (Dale Curtis)'

import os
import shutil
import socket
import tempfile
import unittest

import common_util
import dev_server


# Testing board name.
TEST_BOARD_NAME = 'board-test'

# Test lock name.
TEST_LOCK = 'test-lock'

# Test version string.
TEST_BUILD = '0.99.99.99-r0ABCDEFG-b9999'

# Fake Dev Server Layout:
TEST_LAYOUT = {
    'test-board-1': ['0.1.2.3-r12345678-b12', '0.1.2.4-rAba45678-b126']
}


class DevServerTest(unittest.TestCase):

  def setUp(self):
    self._test_path = tempfile.mkdtemp()
    self._board_path = os.path.join(self._test_path, TEST_BOARD_NAME)

    self._dev = dev_server.DevServer(socket.gethostname(), self._test_path,
                                     os.environ['USER'])

    # Create a fully functional Dev Server layout mimicing the lab deployment.
    os.mkdir(self._board_path)
    for board, builds in TEST_LAYOUT.iteritems():
      board_path = os.path.join(self._test_path, board)
      os.mkdir(board_path)

      with open(os.path.join(board_path, self._dev.LATEST), 'w') as f:
        f.write(builds[-1])

      for build in builds:
        build_path = os.path.join(board_path, build)
        os.mkdir(build_path)
        with open(os.path.join(build_path, self._dev.TEST_IMAGE), 'w') as f:
          f.write(TEST_BUILD)
        with open(os.path.join(build_path,
                               self._dev.STATEFUL_UPDATE), 'w') as f:
          f.write(TEST_BUILD)
        with open(os.path.join(build_path, self._dev.ROOT_UPDATE), 'w') as f:
          f.write(TEST_BUILD)

  def tearDown(self):
    shutil.rmtree(self._test_path)

  def testGetLatestBuildVersion(self):
    with open(os.path.join(self._board_path, self._dev.LATEST), 'w') as f:
      f.write(TEST_BUILD)

    self.assertEquals(self._dev.GetLatestBuildVersion(TEST_BOARD_NAME),
                      TEST_BUILD)

  def testUploadBuildComponents(self):
    # Write text to file so we can verify later, any text will do.
    with open(os.path.join(self._test_path, self._dev.ROOT_UPDATE), 'w') as f:
      f.write(TEST_BUILD)

    with open(os.path.join(self._test_path,
                           self._dev.STATEFUL_UPDATE), 'w') as f:
      f.write(TEST_BUILD)

    with open(os.path.join(self._test_path, self._dev.TEST_IMAGE), 'w') as f:
      f.write(TEST_BUILD)

    au_test_path = os.path.join(self._test_path, self._dev.AU_BASE, 'au_test')
    os.makedirs(au_test_path)
    with open(os.path.join(au_test_path, self._dev.ROOT_UPDATE), 'w') as f:
      f.write(TEST_BUILD)

    self._dev.UploadBuildComponents(remote_dir=self._board_path,
                                    staging_dir=self._test_path,
                                    upload_image=True)

    self.assertTrue(os.path.isfile(os.path.join(self._board_path,
                                                self._dev.TEST_IMAGE)))
    self.assertTrue(os.path.isfile(os.path.join(self._board_path,
                                                self._dev.ROOT_UPDATE)))
    self.assertTrue(os.path.isfile(os.path.join(self._board_path,
                                                self._dev.STATEFUL_UPDATE)))
    # Verify AU symlink and files exist...
    self.assertTrue(os.path.islink(os.path.join(self._board_path,
                                                self._dev.AU_BASE, 'au_test',
                                                self._dev.TEST_IMAGE)))
    self.assertTrue(os.path.isfile(os.path.join(self._board_path,
                                                self._dev.AU_BASE, 'au_test',
                                                self._dev.ROOT_UPDATE)))
    self.assertTrue(os.path.islink(os.path.join(self._board_path,
                                                self._dev.AU_BASE, 'au_test',
                                                self._dev.STATEFUL_UPDATE)))

    with open(os.path.join(self._board_path, self._dev.ROOT_UPDATE), 'r') as f:
      self.assertEquals(f.readlines(), [TEST_BUILD])

    with open(os.path.join(self._board_path,
                           self._dev.STATEFUL_UPDATE), 'r') as f:
      self.assertEquals(f.readlines(), [TEST_BUILD])

    with open(os.path.join(self._board_path, self._dev.TEST_IMAGE), 'r') as f:
      self.assertEquals(f.readlines(), [TEST_BUILD])

    with open(os.path.join(self._board_path, self._dev.AU_BASE, 'au_test',
                           self._dev.ROOT_UPDATE), 'r') as f:
      self.assertEquals(f.readlines(), [TEST_BUILD])

  def testAcquireReleaseLockSuccess(self):
    self.assertTrue(os.path.exists(self._dev.AcquireLock(TEST_LOCK)))
    self._dev.ReleaseLock(TEST_LOCK)

  def testAcquireLockFailure(self):
    self._dev.AcquireLock(TEST_LOCK)
    self.assertRaises(common_util.ChromeOSTestError, self._dev.AcquireLock,
                      TEST_LOCK)
    self._dev.ReleaseLock(TEST_LOCK)

  def testReleaseLockFailure(self):
    self.assertRaises(common_util.ChromeOSTestError,
                      self._dev.ReleaseLock, TEST_LOCK)

  def testUpdateLatestBuild(self):
    self._dev.UpdateLatestBuild(board=TEST_BOARD_NAME, build=TEST_BUILD)

    self.assertTrue(os.path.isfile(os.path.join(self._board_path,
                                                self._dev.LATEST)))

    with open(os.path.join(self._board_path, self._dev.LATEST), 'r') as f:
      self.assertEquals(f.readlines(), [TEST_BUILD + '\n'])

    # Update a second time to ensure n-1 file is created.
    self._dev.UpdateLatestBuild(board=TEST_BOARD_NAME, build=TEST_BUILD + 'n-1')

    self.assertTrue(os.path.isfile(os.path.join(self._board_path,
                                                self._dev.LATEST)))

    self.assertTrue(os.path.isfile(os.path.join(self._board_path,
                                                self._dev.LATEST + '.n-1')))

  def testFindMatchingBoard(self):
    # Try a partial match with a single board.
    self.assertEqual(
        self._dev.FindMatchingBoard(TEST_BOARD_NAME[:-5]),
        [TEST_BOARD_NAME])

    for key in TEST_LAYOUT:
      # Partial match with multiple boards.
      self.assertEqual(
          set(self._dev.FindMatchingBoard(key[:-5])),
          set(TEST_LAYOUT.keys()))

      # Absolute match.
      self.assertEqual(self._dev.FindMatchingBoard(key), [key])

    # Invalid partial match.
    self.assertEqual(self._dev.FindMatchingBoard('asdfsadf'), [])

  def testFindMatchingBuild(self):
    for board, builds in TEST_LAYOUT.iteritems():
      build = builds[0]

      # Try a partial board and build match with single match.
      self.assertEqual(
          self._dev.FindMatchingBuild(board[:-5], build[:-5]),
          [(board, build)])

      # Try a partial board and build match with multiple match.
      self.assertEqual(
          set(self._dev.FindMatchingBuild(board[:-5], build[:5])),
          set([(board, build), (board, builds[1])]))

      # Try very partial board with build match.
      self.assertEqual(
          self._dev.FindMatchingBuild(board[:5], build[:-5]),
          [(board, build)])

  def testPrepareDevServer(self):
    test_prefix = 'abc'
    test_tag = test_prefix + '/123'
    abc_path = os.path.join(self._test_path, test_tag)

    os.mkdir(os.path.join(self._test_path, test_prefix))

    # Verify leaf path is created and proper values returned.
    remote_dir, exists = self._dev.PrepareDevServer(test_tag)
    self.assertEquals(remote_dir, abc_path)
    self.assertFalse(exists)
    self.assertTrue(os.path.exists(abc_path))

    # Test existing remote dir.
    remote_dir, exists = self._dev.PrepareDevServer(test_tag)
    self.assertEquals(remote_dir, abc_path)
    self.assertTrue(exists)
    self.assertTrue(os.path.exists(abc_path))

    # Verify force properly removes the old directory.
    junk_path = os.path.join(remote_dir, 'junk')
    with open(junk_path, 'w') as f:
      f.write('hello!')

    remote_dir, exists = self._dev.PrepareDevServer(test_tag, force=True)
    self.assertEquals(remote_dir, abc_path)
    self.assertFalse(exists)
    self.assertTrue(os.path.exists(abc_path))
    self.assertFalse(os.path.exists(junk_path))

  def testFindDevServerBuild(self):
    # Ensure no matching boards raises exception for latest.
    self.assertRaises(
        common_util.ChromeOSTestError, self._dev.FindDevServerBuild, 'aasdf',
        'latest')

    # Ensure no matching builds or boards raises an exception.
    self.assertRaises(
        common_util.ChromeOSTestError, self._dev.FindDevServerBuild, 'aasdf',
        'asdgsadg')

    # Component functions of FindDevServerBuild are verified elsewhere, so just
    # check exceptions are raised and absolute names return values.
    for board, builds in TEST_LAYOUT.iteritems():
      # Ensure latest returns the proper build.
      self.assertEqual(self._dev.FindDevServerBuild(board, 'latest'),
                       (board, builds[-1]))

      # Ensure specific board, build is returned.
      self.assertEqual(self._dev.FindDevServerBuild(board, builds[0]),
                       (board, builds[0]))

      # Ensure too many matches raises an exception.
      self.assertRaises(
          common_util.ChromeOSTestError, self._dev.FindDevServerBuild, board,
          builds[0][:5])

  def testCloneDevServerBuild(self):
    test_prefix = 'abc'
    test_tag = test_prefix + '/123'
    abc_path = os.path.join(self._test_path, test_tag)

    os.mkdir(os.path.join(self._test_path, test_prefix))

    # Verify leaf path is created and proper values returned.
    board, builds = TEST_LAYOUT.items()[0]
    remote_dir = self._dev.CloneDevServerBuild(board, builds[0], test_tag)
    self.assertEquals(remote_dir, abc_path)
    self.assertTrue(os.path.exists(abc_path))
    self.assertTrue(os.path.isfile(os.path.join(
        abc_path, self._dev.TEST_IMAGE)))
    self.assertTrue(os.path.isfile(os.path.join(
        abc_path, self._dev.ROOT_UPDATE)))
    self.assertTrue(os.path.isfile(os.path.join(
        abc_path, self._dev.STATEFUL_UPDATE)))

    # Verify force properly removes the old directory.
    junk_path = os.path.join(remote_dir, 'junk')
    with open(junk_path, 'w') as f:
      f.write('hello!')
    remote_dir = self._dev.CloneDevServerBuild(
        board, builds[0], test_tag, force=True)
    self.assertEquals(remote_dir, abc_path)
    self.assertTrue(os.path.exists(abc_path))
    self.assertTrue(os.path.isfile(os.path.join(
        abc_path, self._dev.TEST_IMAGE)))
    self.assertTrue(os.path.isfile(os.path.join(
        abc_path, self._dev.ROOT_UPDATE)))
    self.assertTrue(os.path.isfile(os.path.join(
        abc_path, self._dev.STATEFUL_UPDATE)))
    self.assertFalse(os.path.exists(junk_path))

if __name__ == '__main__':
  unittest.main()
