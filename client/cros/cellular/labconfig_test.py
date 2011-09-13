#!/usr/bin/env python
# Copyright (c) 2011 The Chromium OS Authors. All rights reserved.
# Use of this source code is governed by a BSD-style license that can be
# found in the LICENSE file.

import unittest
import labconfig
import json

TEST_CONFIG = {
  'cells': [
    { 'name': 'cell-1' }
  ]
}

class TestLabConfig(unittest.TestCase):
  def setUp(self):
    self.config = labconfig.LabConfig(TEST_CONFIG)

  def test_get_present_cell(self):
    cell = self.config.GetCellByName('cell-1')
    self.assertEqual(cell['name'], 'cell-1')

  def test_get_absent_cell(self):
    self.assertRaises(labconfig.LabConfigError,
                      self.config.GetCellByName,
                      'cell-2')

class TestParseTestArgs(unittest.TestCase):
  def assertParses(self, ret, *args):
    self.assertEqual(ret, labconfig.parse_test_args(args))

  def assertParseFails(self, *args):
    self.assertRaises(labconfig.CellTestArgumentError,
                      labconfig.parse_test_args,
                      args)

  def test_v0_valid(self):
    URL = 'url-foo'
    CELL = 'cell-bar'
    self.assertParses(
        { 'url': URL, 'cell': CELL },
        '0', URL, CELL)

  def test_v0_invalid(self):
    self.assertParseFails('0')
    self.assertParseFails('0', 'foo')
    self.assertParseFails('0', 'foo', 'bar', 'baz')

  def test_invalid_version(self):
    self.assertParseFails('1')
    self.assertParseFails('2')

if __name__ == '__main__':
  unittest.main()
