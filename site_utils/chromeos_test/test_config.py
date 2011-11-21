# Copyright (c) 2011 The Chromium OS Authors. All rights reserved.
# Use of this source code is governed by a BSD-style license that can be
# found in the LICENSE file.

"""Helper class for interacting and loading the JSON ChromeOS Test Config."""

__author__ = 'dalecurtis@google.com (Dale Curtis)'

import json
import optparse
import os
import re


# Test configuration file.
DEFAULT_CONFIG_FILE = 'chromeos_test_config.json'


class TestConfig(object):
  """Utility class for interacting with the JSON ChromeOS Test Config."""

  def __init__(self, config_file=DEFAULT_CONFIG_FILE):
    """Initializes class variables and parses JSON configuration file.

    Args:
      config_file: Path to Chrome OS test configuration file.
    """
    self._config = json.load(open(config_file))

    # Is the config file based off another config?
    if '__base__' in self._config:
      # Rebase the config based on the specified config. Prevent usage of paths.
      base_config = json.load(open(os.path.basename(self._config['__base__'])))
      base_config.update(self._config)
      self._config = base_config

      # Cleanup the base tag.
      del self._config['__base__']

  def GetConfig(self):
    """Returns test configuration object."""
    return self._config

  def ParseConfigGroups(self, board_re=None):
    """Returns 3-tuple of valid boards, groups, and platforms from config.

    Args:
      board_re: If specified, only return platforms for boards matching this
        regular expression.

    Returns:
      Tuple of (boards, groups, platforms)
    """
    boards = sorted(self._config['boards'].keys())
    groups = sorted(self._config['groups'].keys())

    platforms = []
    for board in boards:
      if board_re and not re.search(board_re, board):
        continue
      for platform in self._config['boards'][board]['platforms']:
        platforms.append(platform['platform'])

    platforms = sorted(set(platforms))

    return boards, groups, platforms

  def GetBoardPlatformPairs(self):
    """Returns a generator for (board, platform) defined in the config file.

    Example use:
      for board, platform in testconfig.GetBoardPlatformPairs():
        do_something_neat(board, platform)

    Yields:
      2-tuple of valid (board, platform) defined in the config file.
    """
    for board in self._config['boards']:
      for platform in self._config['boards'][board]['platforms']:
        yield (board, platform['platform'])


def AddOptions(parser):
  """Add command line option group for Test Config.

  Optional method to add helpful command line options to calling programs. Adds
  the option value "config".

  Args:
    parser: OptionParser instance.
  """
  group = optparse.OptionGroup(parser, 'Test Config Options')
  group.add_option('--config', dest='config', default=DEFAULT_CONFIG_FILE,
                   help=('Specify an alternate test configuration file. '
                         'Defaults to "%default".'))
  parser.add_option_group(group)
