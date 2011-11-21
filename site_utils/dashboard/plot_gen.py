# Copyright (c) 2011 The Chromium OS Authors. All rights reserved.
# Use of this source code is governed by a BSD-style license that can be
# found in the LICENSE file.

"""Build index.html and plot .png/.html files for desired perf plots."""

import logging
import os
import re

from django.shortcuts import render_to_response

import dash_util

from dash_view import AutotestDashView

# String resources.
from dash_strings import DASHBOARD_MAIN
from dash_strings import PERF_INDEX_FILE
from dash_strings import PLOT_FILE


def PlotAllNetbook(
    base_dir, dash_view, tpl_netbook, tpl_board):
  """Invoke plot function on all requested plots to create output html files."""

  logging.info('build %s plots into %s', tpl_netbook, base_dir)

  # Produce the main test results + plots combo page for each netbook.
  tpl_last_updated = dash_view.GetFormattedLastUpdated()
  dash_util.SaveHTML(
      os.path.join(base_dir, PLOT_FILE),
      render_to_response(
          os.path.join('tables/details', PLOT_FILE),
          locals()).content)
  # Produce a performance landing page + plots combo page for each netbook.
  dash_util.SaveHTML(
      os.path.join(base_dir, PERF_INDEX_FILE),
      render_to_response(
          os.path.join('tables/details', PERF_INDEX_FILE),
          locals()).content)


def BuildAllPlots(dash_base_dir, dash_view):
  """Build all plots for each netbook and board."""
  for netbook in dash_view.netbooks:
    for board in dash_view.GetNetbookBoardTypes(netbook):
      base_dir = os.path.join(dash_base_dir, netbook, board)
      if not os.path.exists(base_dir):
        dash_util.MakeChmodDirs(base_dir)
      PlotAllNetbook(base_dir, dash_view, netbook, board)


if __name__ == '__main__':
  print 'Run %s with --plot-generate.' % DASHBOARD_MAIN
