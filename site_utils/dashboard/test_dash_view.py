#!/usr/bin/python
# Copyright (c) 2012 The Chromium OS Authors. All rights reserved.
# Use of this source code is governed by a BSD-style license that can be
# found in the LICENSE file.

"""Load dash data model and print output to verify model."""

import logging
import optparse
import os
import sys

import dash_common
import dash_util

settings = 'autotest_lib.frontend.settings'
os.environ['DJANGO_SETTINGS_MODULE'] = settings

from dash_view import AutotestDashView


# String resources.
from dash_strings import LAST_N_JOBS_LIMIT


def parse_args():
  """Support verbose flag."""
  parser = optparse.OptionParser()
  parser.add_option('-d', '--dash-dir',
                    help='base dashboard dir [default: %default]',
                    dest='dashdir',
                    default='/usr/local/autotest/results/dashboard')
  parser.add_option('-f', '--file-name', help='output filename',
                    dest='filename', default=None)
  parser.add_option('-j', '--job-limit', help='limit to last n jobs',
                    dest='joblimit', default=LAST_N_JOBS_LIMIT)
  parser.add_option('-k', '--keyvals',
                    dest='showkeyvals', action='store_true', default=False,
                    help='Take time for keyvals')
  parser.add_option('-n', '--noprint',
                    dest='verbose', action='store_false', default=True,
                    help='Avoid printing data structures')
  parser.add_option('-s', '--show-model',
                    dest='showmodel', action='store_true', default=False,
                    help='Show data structures')
  options, args = parser.parse_args()

  if options.verbose and not options.filename:
    logging.fatal('Must supply --file-name or --noprint.')
    sys.exit(1)

  if options.verbose:
    logging.basicConfig(
        level=logging.DEBUG, filename=options.filename, filemode='w')
  else:
    logging.basicConfig(level=logging.WARNING)
  return options, args


def main():
  diag = dash_util.DebugTiming()

  options, args = parse_args()

  dash_base_dir = options.dashdir
  if not os.path.exists(dash_base_dir):
    dash_util.MakeChmodDirs(dash_base_dir)

  dash_view = AutotestDashView()
  dash_view.CrashSetup(dash_base_dir)
  dash_view.LoadFromDB(int(options.joblimit))
  if options.showmodel:
    dash_view.ShowDataModel()
  del dash_view

  dash_view = AutotestDashView()
  if options.showkeyvals:
    dash_view.CrashSetup(dash_base_dir)
    dash_view.LoadPerfFromDB(int(options.joblimit))
    if options.showmodel:
      dash_view.ShowKeyVals()

  if options.filename:
    os.chmod(options.filename, 0644)

  del diag


if __name__ == '__main__':
  main()
