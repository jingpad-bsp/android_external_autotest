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
    self.base_config = labconfig.LabConfig(TEST_CONFIG)
    self.json_config = labconfig.JsonLabConfig(json.dumps(TEST_CONFIG))

  def _test_get_cell_by_name(self, config):
    cell = config.GetCellByName('cell-1')
    self.assertEqual(cell['name'], 'cell-1')
    self.assertRaises(labconfig.ConfigError, config.GetCellByName, 'cell-2')

  def test_base_get_cell_by_name(self):
    self._test_get_cell_by_name(self.base_config)

  def test_json_get_cell_by_name(self):
    self._test_get_cell_by_name(self.json_config)

if __name__ == '__main__':
  unittest.main()
