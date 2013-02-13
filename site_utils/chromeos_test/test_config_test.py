#!/usr/bin/python
#
# Copyright (c) 2011 The Chromium OS Authors. All rights reserved.
# Use of this source code is governed by a BSD-style license that can be
# found in the LICENSE file.
# pylint: disable-msg=C0111
"""Unit tests for TestConfig class."""

__author__ = 'dalecurtis@google.com (Dale Curtis)'

import json
import optparse
import os
import shutil
import tempfile
import unittest

import test_config


# Fake platform name.
_SAMPLE_PLATFORM = 'netbook_TEST'

# Fake test config layout.
_SAMPLE_TEST_CONFIG_NAME = 'test_config.json'
_SAMPLE_TEST_CONFIG = {
    "boards": {
        "test-board-1": {
            "archive_server": "http://awesometown/dev-channel",
            "archive_path": "test-board-1/%(build_version)s/test.zip",
            "build_pattern": "0\\.1\\..*",
            "platforms": [
                {"platform": _SAMPLE_PLATFORM,  "extra_groups": ["abc"]}
            ]
        }
    },

    "default_groups": [
        "tests_a", "tests_b"
    ],

    "groups": {
        "test_a": [
            {"name": "a",
             "control": "tests/suites/control.a"}
        ],

        "test_b": [
            {"name": "b",
             "control": "tests/suites/control.b"}
        ]
    },

    "import_hosts": [
        {
            "host": "test.corp.google.com",
            "path": "/usr/local/autotest",
            "user": "chromeos-test"
        }
    ],

    "dev_server": {
        "host": "127.0.0.1",
        "path": "/usr/local/google/images",
        "user": "testing"
    },

    "appengine": {
        "dash_url": "https://localhost",
        "upload_from": "test.corp.google.com"
    }
}

_SAMPLE_OVERRIDE_CONFIG_NAME = 'test_override.json'
_SAMPLE_OVERRIDE_CONFIG = {
    "__base__": _SAMPLE_TEST_CONFIG_NAME,

    "boards": {
        "test-board-2": {
            "platforms": [
                {"platform": _SAMPLE_PLATFORM}
            ]
        }
    },

    "default_groups": ["test_c"],

    "groups": {
        "test_c": [
            {"name": "c",
             "control": "tests/suites/control.c"}
        ]
    }
}


class TestConfigTest(unittest.TestCase):

  def setUp(self):
    self._test_path = tempfile.mkdtemp()
    self._test_config_path = os.path.join(
        self._test_path, _SAMPLE_TEST_CONFIG_NAME)
    self._test_override_config_path = os.path.join(
        self._test_path, _SAMPLE_OVERRIDE_CONFIG_NAME)

    with open(self._test_config_path, 'w') as f:
      json.dump(_SAMPLE_TEST_CONFIG, f)

    with open(self._test_override_config_path, 'w') as f:
      json.dump(_SAMPLE_OVERRIDE_CONFIG, f)

    self._config = test_config.TestConfig()

    self._test_config = test_config.TestConfig(self._test_config_path)

    shutil.copy(test_config.DEFAULT_CONFIG_FILE, self._test_path)
    cwd = os.getcwd()
    os.chdir(self._test_path)
    self._override_config = test_config.TestConfig(
        self._test_override_config_path)
    os.chdir(cwd)

  def tearDown(self):
    shutil.rmtree(self._test_path)

  def testValidConfig(self):
    self.assertEquals(sorted(self._config.GetConfig().keys()),
                      sorted(['appengine', 'boards', 'default_groups',
                              'dev_server', 'groups', 'import_hosts',
                              'default_tot_groups']))

  def testParseConfigGroups(self):
    boards, groups, platforms = self._test_config.ParseConfigGroups()

    self.assertEqual(set(boards), set(_SAMPLE_TEST_CONFIG['boards'].keys()))
    self.assertEqual(set(groups), set(_SAMPLE_TEST_CONFIG['groups'].keys()))
    self.assertEqual(platforms, [_SAMPLE_PLATFORM])

    boards, groups, platforms = self._override_config.ParseConfigGroups()
    self.assertEqual(set(boards), set(_SAMPLE_OVERRIDE_CONFIG['boards'].keys()))
    self.assertEqual(set(groups), set(_SAMPLE_OVERRIDE_CONFIG['groups'].keys()))
    self.assertEqual(platforms, [_SAMPLE_PLATFORM])

    _, _, platforms = self._test_config.ParseConfigGroups(board_re='wont match')
    self.assertEqual([], platforms)

    _, _, platforms = self._test_config.ParseConfigGroups(board_re='test')
    self.assertEqual(platforms, [_SAMPLE_PLATFORM])

  def testParseOptionsConfig(self):
    parser = optparse.OptionParser()
    test_config.AddOptions(parser)

    self.assertEqual(
        parser.parse_args(['--config', 'tests.json'])[0].config, 'tests.json')

  def testOverrideConfig(self):
    self.assertTrue(not '__base__' in self._override_config.GetConfig())
    for key in self._test_config.GetConfig().keys():
      self.assertTrue(key in self._override_config.GetConfig())


if __name__ == '__main__':
  unittest.main()
