#!/usr/bin/python
# Copyright (c) 2011 The Chromium OS Authors. All rights reserved.
# Use of this source code is governed by a BSD-style license that can be
# found in the LICENSE file.

"""Load dash data model and analyze data."""

import logging
import optparse
import os

import dash_common
import dash_util

settings = 'autotest_lib.frontend.settings'
os.environ['DJANGO_SETTINGS_MODULE'] = settings

from dash_view import AutotestDashView


# String resources.
from dash_strings import LAST_N_JOBS_LIMIT


def test_first_two_keyval_data_points(dash_view, dash_options):
  """Show analysis of the effect of dropping first two points."""
  float_converter = dash_util.HumanReadableFloat()
  boards = dash_view.GetBoardTypes()

  summary = {}

  # Print stats for each build/key that has an 'out of range' first or second
  # data point.
  for board in boards:
    netbooks = dash_view.GetNetbooksWithBoardTypeCategory(board, "perfalerts")
    board_summary = summary.setdefault(board, {})
    for netbook in netbooks:
      keyvals = dash_view.GetTestKeyVals(
          netbook, board, "platform_BootPerfServer")
      if not keyvals:
        continue
      netbook_summary = board_summary.setdefault(netbook, {})
      for key, build_dict in keyvals.iteritems():
        key_summary = netbook_summary.setdefault(key, {
            'sum1': 0.0, 'sum2': 0.0, 'summinus2': 0.0,
            'count1': 0, 'countminus2': 0, 'build_averages': {}})
        key_printed = False
        for seq, data_tuple in build_dict.iteritems():
          data = data_tuple[0]
          list_len = len(data)
          key_summary['build_averages'][seq] = sum(data, 0.0) / list_len
          if list_len > 2:
            key_summary['sum1'] += data[0]
            key_summary['sum2'] += data[1]
            sum_minus2 = sum(data[2:], 0.0)
            len_minus2 = list_len - 2
            key_summary['summinus2'] += sum_minus2
            key_summary['count1'] += 1
            key_summary['countminus2'] += len_minus2
            list_avg = sum_minus2 / len_minus2
            d = list_avg * 0.1
            if not dash_options.datapoints:
              continue
            if (abs(data[0]-list_avg) > d or
                abs(data[1]-list_avg) > d):
              if not key_printed:
                logging.debug('%s-%s-%s:', board, netbook, key)
                key_printed = True
              logging.debug('%s, %s, %s, %s', board, netbook, key, seq)
              logging.debug('  %s', [float_converter.Convert(n) for n in data])

  # Now print a summary.
  if dash_options.summaryaverages:
    logging.debug('-----------------------------')
    logging.debug('SUMMARY:')
    logging.debug(
        '  AVG1     AVG2   AVGALL-2  AVG-ALL    '
        'BOARD       NETBOOK       KEY')
    for board, netbooks in summary.iteritems():
      for netbook, keys in netbooks.iteritems():
        for key, key_stats in keys.iteritems():
          logging.debug(
              '%8s %8s %8s %8s %s %s %s',
              float_converter.Convert(
                  key_stats['sum1'] / key_stats['count1']),
              float_converter.Convert(
                  key_stats['sum2'] / key_stats['count1']),
              float_converter.Convert(
                  key_stats['summinus2'] / key_stats['countminus2']),
              float_converter.Convert(
                  (key_stats['sum1'] + key_stats['sum2'] +
                   key_stats['summinus2']) / (
                      key_stats['count1'] * 2 + key_stats['countminus2'])),
              board, netbook, key)
  if dash_options.buildaverages:
    logging.debug('-----------------------------')
    for board, netbooks in summary.iteritems():
      for netbook, keys in netbooks.iteritems():
        for key, key_stats in keys.iteritems():
          for seq, build_average in key_stats['build_averages'].iteritems():
            logging.debug(
                '%s, %s, %s, %s: %s',
                board, netbook, key, seq,
                float_converter.Convert(build_average))


def parse_args():
  """Support verbose flag."""
  parser = optparse.OptionParser()
  parser.add_option('-b', '--print-build-averages', help='show build averages',
                    dest='buildaverages', action='store_true', default=False)
  parser.add_option('-f', '--file-name', help='output filename',
                    dest='filename', default=None)
  parser.add_option('-j', '--job-limit', help='limit to last n jobs',
                    dest='joblimit', default=LAST_N_JOBS_LIMIT)
  parser.add_option('-d', '--print-data-points', help='show data point values',
                    dest='datapoints', action='store_true', default=False)
  parser.add_option('-s', '--print-summary', help='show summary of averages',
                    dest='summaryaverages', action='store_true', default=False)
  options, args = parser.parse_args()
  logging_level = logging.DEBUG
  if options.filename:
    logging.basicConfig(
        level=logging.DEBUG, filename=options.filename, filemode='w')
  else:
    logging.basicConfig(level=logging_level)
  return options, args


def main():
  options, args = parse_args()

  dash_view = AutotestDashView()
  dash_view.LoadPerfFromDB(int(options.joblimit))
  test_first_two_keyval_data_points(dash_view, options)

  if options.filename:
    os.chmod(options.filename, 0644)

if __name__ == '__main__':
  main()
