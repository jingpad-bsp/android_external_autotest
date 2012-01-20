#!/usr/bin/python
# Copyright (c) 2011 The Chromium OS Authors. All rights reserved.
# Use of this source code is governed by a BSD-style license that can be
# found in the LICENSE file.

"""Document test and email options in an html table for readability."""

import commands
import datetime
import getpass
import json
import logging
import optparse
import os
import sys

# dash_common and dash_view needed first for anything db or django related.
import dash_common
import dash_util
from dash_view import AutotestDashView

from django.shortcuts import render_to_response

import gviz_api


def ParseArgs(argv):
  base_dir = os.path.dirname(os.path.abspath(argv[0]))

  parser = optparse.OptionParser()
  parser.add_option('-d', '--dash-dir', help='base dashboar dir',
                    dest='dashdir', default=None)
  parser.add_option('-p', '--profile', help='Enable profiling of execution',
                    dest='profiler', action='store_true', default=False)
  parser.add_option('-v', '--verbose', help='Show more output',
                    dest='verbose', action='store_true', default=False)
  options, args = parser.parse_args()

  logging_level = logging.INFO
  if options.verbose:
    logging_level = logging.DEBUG

  logging.basicConfig(level=logging_level)

  return options, base_dir


def SetOutputDir(options):
  me = getpass.getuser()
  if options.dashdir:
    dash_base_dir = options.dashdir
  else:
    dash_base_dir = '/home/%s/www/dash' % me

  if not os.path.exists(dash_base_dir):
    os.makedirs(dash_base_dir)
    os.chmod(dash_base_dir, 0755)

  logging.info('Using dir: %s.', dash_base_dir)
  return dash_base_dir


def GetJSONOptions(current_dir, json_file):
  if not os.path.exists(json_file):
    json_file = os.path.join(current_dir, json_file)
    if not os.path.exists(json_file):
      return None
  return json.load(open(json_file))


def ParseTestConfig(config_dict, test_json):
  # groups is a dictionary mapping test groups to a list of categories.
  groups = {}
  for group, categories in test_json['groups'].iteritems():
    groups[group] = [category['name'] for category in categories]

  # default_categories is list of the default categories to be tested.
  default_categories = []
  for group in test_json['default_groups']:
    default_categories.extend(groups[group])

  # Attempt to determine which test suites (categories) will be run on
  # each board/netbook.
  for board, board_dict in test_json['boards'].iteritems():
    if not 'platforms' in board_dict:
      logging.warning('Platforms missing from test config for %s.', board)
      continue
    for platform_dict in board_dict['platforms']:
      if not 'platform' in platform_dict:
        logging.warning(
            'Platform missing from test config for %s.', platform_dict)
        continue
      netbook = platform_dict['platform']
      netbook_dict = config_dict.setdefault(netbook, {})
      board_dict = netbook_dict.setdefault(board, {})
      if 'groups' in platform_dict:
        # Does not run default_categories.
        categories = []
        for group in platform_dict['groups']:
          categories.extend(groups[group])
      else:
        # Runs default_categories and extra if found.
        categories = default_categories[:]
        if 'extra_groups' in platform_dict:
          for extra_group in platform_dict['extra_groups']:
            categories.extend(groups[extra_group])
      for category in categories:
        board_dict.setdefault(category, {})


def ParseDashConfig(config_dict, dash_json):
  # Show the email targets in a readable manner.
  for mail_config in dash_json['resultmail']:
    for email_filter in mail_config['filters']:
      # chromeos-bvt is special since it is automatically
      # included when sheriffs is True.
      sheriffs = chromeos_bvt = email_filter.get('sheriffs', False)
      cc = [f.split('@')[0] for f in email_filter['cc']]
      if 'chromeos-bvt' in cc:
        chromeos_bvt = True
        cc.remove('chromeos-bvt')
      if 'chromeos-tpms' in cc:
        chromeos_tpms = True
        cc.remove('chromeos-tpms')
      else:
        chromeos_tpms = None
      trigger = email_filter.get('trigger', 'result_changed')
      for netbook, boards in mail_config['platforms'].iteritems():
        netbook_dict = config_dict.setdefault(netbook, {})
        for board in boards:
          board_dict = netbook_dict.setdefault(board, {})
          for category in email_filter['categories']:
            cat_dict = board_dict.setdefault(category, {})
            cat_dict['sheriffs'] = sheriffs
            cat_dict['chromeos-bvt'] = chromeos_bvt
            cat_dict['chromeos-tpms'] = chromeos_tpms
            cat_dict['others'] = ', '.join(cc)
            cat_dict['emailcondition'] = trigger
  for email_alert in dash_json['alerts']:
    for platform in email_alert['platforms']:
      for board, netbook in platform.iteritems():
        netbook_dict = config_dict.setdefault(netbook, {})
        board_dict = netbook_dict.setdefault(board, {})
        for category in email_alert['categories']:
          cat_dict = board_dict.setdefault(category, {})
          cat_dict['alerts'] = email_alert['test']


def AggregateRows(config_dict):
  """Convert the hierarchical config dict into a list of dicts.

  Google visualisation chart api's easily consume a list of dicts
  where each dict corresponds to a row in the table and each key
  to a column.
  """
  table_rows = []
  table_columns = ('sheriffs', 'chromeos-bvt', 'chromeos-tpms',
                   'others', 'emailcondition', 'alerts')
  for netbook, netbook_dict in config_dict.iteritems():
    for board, board_dict in netbook_dict.iteritems():
      for category, cat_dict in board_dict.iteritems():
        this_row = {'netbook': netbook,
                    'board': board,
                    'category': category}
        for attribute in table_columns:
          # Need False to print as None (blank).
          if not cat_dict.get(attribute):
            this_row[attribute] = None
          else:
            this_row[attribute] = cat_dict[attribute]
        table_rows.append(this_row)
  return table_rows, ('netbook', 'board', 'category') + table_columns


def ToGVizJsonTable(table_rows, table_columns):
  """Format for Google visualizations table."""
  description = {}
  for c in table_columns:
    description[c] = ('string', c)
  gviz_data_table = gviz_api.DataTable(description)
  gviz_data_table.LoadData(table_rows)
  gviz_data_table = gviz_data_table.ToJSon(table_columns)
  return gviz_data_table


def DoWork(options, base_dir):
  dash_base_dir = SetOutputDir(options)
  config_dict = {}
  ParseTestConfig(
      config_dict,
      GetJSONOptions(base_dir, 'chromeos_test_config.json'))
  ParseDashConfig(
      config_dict,
      GetJSONOptions(base_dir, 'dash_config.json'))
  tpl_rows = ToGVizJsonTable(*AggregateRows(config_dict))
  tpl_last_updated = datetime.datetime.ctime(datetime.datetime.now())
  dash_util.SaveHTML(
      os.path.join(dash_base_dir, 'test_config_table.html'),
      render_to_response(
          os.path.join('tables/configs', 'test_config.html'),
          locals()).content)


def main(argv):
  options, base_dir = ParseArgs(argv)
  do_work = 'DoWork(options, base_dir)'
  if options.profiler:
    logging.info('Profiling...')
    import tempfile, cProfile, pstats
    base_filename = os.path.basename(os.path.abspath(argv[0]))
    pname = os.path.join(tempfile.gettempdir(),
                         '%s.profiler.out' % base_filename)
    logging.debug('Using profile file: %s.', pname)
    cProfile.runctx(do_work, globals=globals(), locals=locals(),
                    filename=pname)
    p = pstats.Stats(pname)
    p.sort_stats('cumulative').print_stats(20)
    pngname = os.path.join(tempfile.gettempdir(), '%s.png' % base_filename)
    png_command = 'python %s -f pstats %s | dot -Tpng -o %s' % (
        os.path.join(base_dir, 'external', 'gprof2dot.py'), pname, pngname)
    commands.getoutput(png_command)
  else:
    exec(do_work)


if __name__ == '__main__':
  main(sys.argv)
