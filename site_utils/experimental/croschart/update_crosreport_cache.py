#!/usr/bin/python
# Copyright (c) 2011 The Chromium OS Authors. All rights reserved.
# Use of this source code is governed by a BSD-style license that can be
# found in the LICENSE file.

"""Update cache entries for interval reports in cros-reports."""

import commands
import logging
import os
import optparse
import pprint
import json
import sys


RELEASE_COUNT = 2
REPORT_SERVER = 'cros-reports'
REPORT_URL = 'croschart/server/chart'
CONFIG_FILE = 'croschart_defaults.json'
WGET_CMD = 'wget --timeout=120 --tries=1 --no-proxy -qO- '


def GatherBoardSystemsReleases(release_count):
  """Retrieve a list of boards and systems."""
  url = 'http://cautotest/results/dashboard/waterfall_index.html'
  command = '%s %s' % (WGET_CMD, url)
  results = commands.getoutput(command)
  tables = results.split('<table')
  # Retrieve boards/systems.
  rows = tables[1].split('<tr>')
  cols = rows[1].split('<th')
  board_systems = []
  for col in cols[2:]:
    fields = col.split('<br>')
    board = fields[0].split()[2].strip()
    system = fields[1].split('\n')[1].strip().replace(' ', '_')
    board_systems.append((board, system))
  logging.debug('board-systems: %s', pprint.pformat(board_systems))
  # Retrieve releases.
  row_base = 2
  row_max = min(len(rows), row_base + release_count)
  releases = [r.split('\n')[1].split('>')[1].split('<')[0]
              for r in rows[row_base:row_max]]
  logging.debug('releases: %s', pprint.pformat(releases))
  return board_systems, releases


def ReadInputFile(input_file):
  """Read the input file into a string list."""
  f = open(input_file, 'r')
  chart_list = json.load(f)
  f.close()
  return chart_list


def UpdateCache(options, board_systems, releases, chart_list):
  """Run a command to update the chart in the cache."""
  for board, system in board_systems:
    for release in releases:
      for test_name, key_list in chart_list:
        urlparams = ['testkey=%s,%s&interval=2,week' % (test_name, key_list)]
        urlparams.append('&board=%s-%s&system=%s' % (board, release, system))
        urlparams.append('&updatecache=true')
        url = '"http://%s/%s?%s"' % (options.reportserver, REPORT_URL,
                                     ''.join(urlparams))
        command = '%s %s' % (WGET_CMD, url)
        logging.debug(command)
        if not options.testmode:
          results = commands.getoutput(command)
          logging.debug(results)


def ParseArgs(argv):
  """Get input and output file."""
  base_dir = os.path.dirname(os.path.abspath(argv[0]))

  parser = optparse.OptionParser()
  parser.add_option('-c', '--report-config',
                    help='report config file (json)',
                    dest='reportconfig', default=CONFIG_FILE)
  parser.add_option('-r', '--release-count', type="int",
                    help='qty of past releases to hit [default: %default]',
                    dest='releasecount', default=RELEASE_COUNT)
  parser.add_option('-s', '--report-server',
                    help='server for reports page',
                    dest='reportserver', default=REPORT_SERVER)
  parser.add_option('-t', '--test-mode',
                    help='Does not run commands.',
                    dest='testmode', action='store_true', default=False)
  parser.add_option('-v', '--verbose',
                    help='Show more output',
                    dest='verbose', action='store_true', default=False)
  options, args = parser.parse_args()

  logging_level = logging.INFO
  if options.verbose:
    logging_level = logging.DEBUG

  logging.basicConfig(level=logging_level)

  return options, args, base_dir


def main(argv):
  """Request all typical reports."""
  options, args, base_dir = ParseArgs(argv)

  logging.debug('Using input file: %s', options.reportconfig)
  logging.debug('Using reporting server http://%s', options.reportserver)

  board_systems, releases = GatherBoardSystemsReleases(options.releasecount)
  chart_list = ReadInputFile(options.reportconfig)
  UpdateCache(options, board_systems, releases, chart_list)


if __name__ == '__main__':
  main(sys.argv)
