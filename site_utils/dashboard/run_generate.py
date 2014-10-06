#!/usr/bin/python
# Copyright (c) 2012 The Chromium OS Authors. All rights reserved.
# Use of this source code is governed by a BSD-style license that can be
# found in the LICENSE file.

"""Master chromeos test dashboard/email driver - called by cron."""

import commands
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

from alert_email import AlertAll
from build_info import BuildInfo
from dash_email import EmailAllFailures
from dash_email import EmailFromConfig
from plot_gen import BuildAllPlots
from table_gen import BuildAllTables

# String resources.
from dash_strings import AUTOTEST_USER
from dash_strings import LAST_N_JOBS_LIMIT
from dash_strings import SUMMARY_TABLE_ROW_LIMIT


def ParseArgs(argv):
  base_dir = os.path.dirname(os.path.abspath(argv[0]))

  parser = optparse.OptionParser()
  parser.add_option('-a', '--alert-generate',
                    help='regression alert email [default: %default]',
                    dest='alertgenerate', action='store_true', default=False)
  parser.add_option('-c', '--config-file',
                    help='config file [default: %default]',
                    dest='configfile', default="dash_config.json")
  parser.add_option('-d', '--dash-dir',
                    help='base dashboar dir [default: %default]',
                    dest='dashdir',
                    default='/usr/local/autotest/results/dashboard')
  parser.add_option('-j', '--job-limit',
                    help='limit to last n jobs [default: %default]',
                    dest='joblimit', type='int', default=LAST_N_JOBS_LIMIT)
  parser.add_option('-k', '--keep-build-cache',
                    help='avoid pruning cache [default: %default]',
                    dest='keepbuildcache', action='store_true', default=False)
  parser.add_option('-m', '--mail-generate',
                    help='send failure emails [default: %default]',
                    dest='mailgenerate', action='store_true', default=False)
  parser.add_option('-n', '--no-execute',
                    help='Do not execute subcommands [default: %default]',
                    dest='noexecute', action='store_true', default=False)
  parser.add_option('-p', '--plot-generate',
                    help='build dash test plots [default: %default]',
                    dest='plotgenerate', action='store_true', default=False)
  parser.add_option('-t', '--table-generate',
                    help='build dash test tables [default: %default]',
                    dest='tablegenerate', action='store_true', default=False)
  parser.add_option('', '--summary-limit',
                    help='max rows in summaries [default: %default]',
                    dest='summarylimit', type='int',
                    default=SUMMARY_TABLE_ROW_LIMIT)
  parser.add_option('', '--waterfall-limit',
                    help='max rows in waterfall summaries [default: %default]',
                    dest='waterfalllimit', type='int',
                    default=SUMMARY_TABLE_ROW_LIMIT)
  parser.add_option('', '--profile',
                    help='Enable profiling of execution [default: %default]',
                    dest='profiler', action='store_true', default=False)
  parser.add_option('-v', '--verbose',
                    help='Show more output [default: %default]',
                    dest='verbose', action='store_true', default=False)
  options, args = parser.parse_args()

  logging_level = logging.INFO
  if options.verbose:
    logging_level = logging.DEBUG

  logging.basicConfig(level=logging_level)

  return options, base_dir


def CheckOptions(options):
  dash_base_dir = ''
  if (not options.alertgenerate and
      not options.mailgenerate and
      not options.plotgenerate and
      not options.tablegenerate):
    logging.fatal(
        'Must supply at least 1 command from: '
        '--alert-generate, --mail-generate, '
        '--plot-generate or --table-generate.')
    sys.exit(1)

  me = getpass.getuser()
  if options.dashdir:
    dash_base_dir = options.dashdir
  elif me == AUTOTEST_USER:
    dash_base_dir = '/usr/local/autotest/results/dashboard'
  else:
    dash_base_dir = '/home/%s/www/dash' % me

  if not os.path.exists(dash_base_dir):
    dash_util.MakeChmodDirs(dash_base_dir)

  logging.info("Using dir: %s.", dash_base_dir)
  return dash_base_dir


def GetJSONOptions(current_dir, json_file):
  if not os.path.exists(json_file):
    json_file = os.path.join(current_dir, json_file)
    if not os.path.exists(json_file):
      return None
  return json.load(open(json_file))


def DoWork(options, base_dir):
  diag = dash_util.DebugTiming()
  dash_base_dir = CheckOptions(options)
  # Umask needed for permissions on created dirs.
  prev_dir = os.getcwd()
  os.chdir(dash_base_dir)
  prev_umask = os.umask(0)

  # Dash config file sets things up.
  dash_options = GetJSONOptions(base_dir, options.configfile)
  if not dash_options:
    logging.fatal('Missing config.')
    sys.exit(1)

  # Populate data model.
  dash_view = AutotestDashView()
  dash_view.CrashSetup(dash_base_dir)
  dash_view.SetDashConfig(dash_options)
  if not options.noexecute:
    dash_view.LoadFromDB(options.joblimit)

  # Build info singleton cache for performance improvement.
  build_info = BuildInfo()

  if options.tablegenerate:
    logging.info("Generating tables.")
    if not options.noexecute:
      BuildAllTables(dash_base_dir, dash_view, dash_options,
                     options.summarylimit, options.waterfalllimit)

  if options.mailgenerate:
    logging.info("Generating email.")
    if not options.noexecute:
      EmailFromConfig(dash_base_dir, dash_view, dash_options)
    if not options.noexecute:
      EmailAllFailures(dash_base_dir, dash_view)

  if options.plotgenerate:
    logging.info("Generating plots.")
    if not options.noexecute:
      BuildAllPlots(dash_base_dir, dash_view)

  if options.alertgenerate:
    logging.info("Generating alerts.")
    if not options.noexecute:
      dash_view.LoadPerfFromDB(options.joblimit)
      AlertAll(dash_base_dir, dash_view, dash_options)

  if not options.keepbuildcache:
    if not options.noexecute:
      build_info.PruneTmpFiles(dash_view)

  os.umask(prev_umask)
  os.chdir(prev_dir)
  del diag


def main(argv):
  """Can generate tables, plots and email."""
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
    logging.debug(png_command)
    commands.getoutput(png_command)
  else:
    exec(do_work)


if __name__ == '__main__':
  main(sys.argv)
