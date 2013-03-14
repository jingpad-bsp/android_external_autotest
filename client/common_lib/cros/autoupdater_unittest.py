#!/usr/bin/python
# Copyright (c) 2013 The Chromium OS Authors. All rights reserved.
# Use of this source code is governed by a BSD-style license that can be
# found in the LICENSE file.

import unittest

import common

import autoupdater


class TestAutoUpdater(unittest.TestCase):
    """Test autoupdater module."""


    def testParseBuildFromUpdateUrlwithUpdate(self):
        """Test that we properly parse the build from an update_url."""
        update_url = ('http://172.22.50.205:8082/update/lumpy-release/'
                      'R27-3837.0.0')
        expected_value = 'lumpy-release/R27-3837.0.0'
        self.assertEqual(autoupdater.url_to_image_name(update_url),
                         expected_value)


if __name__ == '__main__':
  unittest.main()
