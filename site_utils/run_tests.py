#!/usr/bin/python
#
# Copyright (c) 2011 The Chromium OS Authors. All rights reserved.
# Use of this source code is governed by a BSD-style license that can be
# found in the LICENSE file.

"""Tool for running test groups against different ChromeOS boards and platforms.

run_tests allows users to execute test groups against Autotest hosts. Will
create Autotest jobs given a board, platform, and list of test groups. Test
groups are configurable via a JSON configuration file.

run_tests will create jobs using a specialized control file which will update
the targeted hosts to a specific board type and build version before running
jobs against them.
"""

__author__ = 'dalecurtis@google.com (Dale Curtis)'

import logging
import optparse

from chromeos_test import autotest_util
from chromeos_test import dev_server
from chromeos_test import log_util
from chromeos_test import test_config
import test_scheduler


def ParseOptions():
  """Parse command line options. Returns 2-tuple of options and config."""
  # If default config exists, parse it and use values for help screen.
  config = test_config.TestConfig()

  # If config is provided parse values to make help screen more useful.
  boards, groups, platforms = config.ParseConfigGroups()

  parser = optparse.OptionParser(
      'usage: %prog --board <BOARD> --platform <PLATFORM> [options]')
  parser.add_option('--board', dest='board',
                    help=('Run tests only on the specified board. Valid boards:'
                          ' %s' % boards))
  parser.add_option('--build', dest='build',
                    help='Specify the build version to process.')
  parser.add_option('--groups', dest='groups',
                    help=('Comma separated list of test groups. Valid groups:'
                          ' %s' % groups))
  parser.add_option('--platform', dest='platform',
                    help=('Run tests on the specified platform. Valid platforms'
                          ': %s' % platforms))

  # Add utility/helper class command line options.
  test_config.AddOptions(parser)
  autotest_util.AddOptions(parser, cli_only=True)

  options = parser.parse_args()[0]

  if not options.board or not options.platform:
    parser.error('A board and platform must be provided.')

  # Load correct config file if alternate is specified.
  if options.config != test_config.DEFAULT_CONFIG_FILE:
    config = test_config.TestConfig(options.config)
    boards, groups, platforms = config.ParseConfigGroups()

  if not options.groups:
    options.groups = config.GetConfig()['default_groups']
  else:
    options.groups = options.groups.split(',')

  if not options.board in boards:
    parser.error('Invalid board "%s" specified. Valid boards are: %s'
                 % (options.board, boards))

  for group in options.groups:
    if not group in groups:
      parser.error('Invalid group "%s" specified. Valid groups are: %s'
                   % (group, groups))

  if not options.platform in platforms:
    parser.error('Invalid platform "%s" specified. Valid platforms are: %s'
                 % (options.platform, platforms))

  return options, config.GetConfig()


def main():
  options, config = ParseOptions()

  # Setup logger and enable verbose mode.
  log_util.InitializeLogging(True)

  logging.info('------------[ Processing board %s ]------------', options.board)

  # Initialize Dev Server Utility class.
  dev = dev_server.DevServer(**config['dev_server'])

  # Get latest version for this board.
  if options.build:
    build = options.build
  else:
    build = dev.GetLatestBuildVersion(options.board)

  logging.info('Latest build version available on Dev Server is %s.', build)

  tr = test_scheduler.TestRunner(
      board=options.board, build=build, cli=options.cli, config=config, dev=dev)

  tr.RunTestGroups(groups=options.groups, lock=False, platform=options.platform)


if __name__ == '__main__':
  main()
