# Copyright (c) 2012 The Chromium OS Authors. All rights reserved.
# Use of this source code is governed by a BSD-style license that can be
# found in the LICENSE file.

"""Generate detail table .html files for board-netbook-testcategories."""

import datetime
import logging
import os

from django.shortcuts import render_to_response

import dash_util

from build_info import BuildInfo
from dash_view import SummaryRanges
from table_builder import TableBuilder

# String resources.
from dash_strings import BVT_TAG
from dash_strings import DASHBOARD_MAIN
from dash_strings import EMAILS_SUMMARY_FILE
from dash_strings import KERNEL_TABLE_FILE
from dash_strings import KERNEL_WATERFALL_FILE
from dash_strings import KERNELTEST_TAG
from dash_strings import PERF_BUILDS_FILE
from dash_strings import TEST_DETAILS_FILE
from dash_strings import TEST_LANDING_FILE
from dash_strings import TEST_WATERFALL_FILE
from dash_strings import UNKNOWN_TIME_STR


def _BuildNetbookHTML(
    dash_base_dir, dash_view, tpl_netbook, tpl_board,
    default_category, dash_options):
  """Create table files for all categories of a netbook-board.

  Produces a set of pages of test results for a given netbook,
  board and categories with tests executed.

  Args:
    dash_base_dir: base of dashboard output files.
    dash_view: data model with all test result details.
    tpl_netbook: netbook (e.g. netbook_MARIO_MP) for these pages.
    tpl_board: board (e.g. x86-mario) for these pages.
    default_category: landing page when switching pages.
    dash_options: config options used for setting landing pages.
  """
  base_dir = os.path.join(dash_base_dir, tpl_netbook, tpl_board)
  if not os.path.exists(base_dir):
    dash_util.MakeChmodDirs(base_dir)
  logging.info('build %s into %s', tpl_netbook, base_dir)

  # Build a details page for each category.
  alternate_landings = dash_options.get('alternatelandings', {})
  tpl_board_netbooks = [
      (n, alternate_landings.get(tpl_board, {}).get(n, BVT_TAG))
      for n in dash_view.GetNetbooksWithBoardType(tpl_board)
      if n != tpl_netbook]
  tpl_other_boards = sorted(
      [b
       for b in dash_view.GetNetbookBoardTypes(tpl_netbook)
       if b != tpl_board])
  tpl_last_updated = dash_view.GetFormattedLastUpdated()

  tpl_categories = dash_view.GetUICategories(tpl_netbook, tpl_board)
  if not default_category in tpl_categories:
    tpl_categories.append(default_category)
  tpl_categories.sort()

  tpl_categories_with_color = []
  for tpl_category in tpl_categories:
    table_builder = TableBuilder(dash_base_dir, tpl_netbook, tpl_board,
                                 tpl_category)
    total, failed = table_builder.CountTestList()
    if failed:
      label = tpl_category + '(%d/%d)' % (total, failed)
    else:
      label = tpl_category + '(%d)' % total
    if total == 0:
      bg_class = 'white'
    elif failed == 0:
      bg_class = 'success'
    elif total == failed:
      bg_class = 'failure'
    else:
      bg_class = 'warning'
    tpl_categories_with_color.append(
        (tpl_category, table_builder, label, bg_class))

  # Produce a test results page for each test category.
  tpl_perf_builds = None
  for tpl_category, table_builder, label, bg_class in tpl_categories_with_color:
    tpl_tables = table_builder.BuildTables()
    if tpl_category == BVT_TAG and tpl_tables:
      tpl_perf_builds = tpl_tables[0]['body']
    dash_util.SaveHTML(
        os.path.join(base_dir, '%s.html' % tpl_category),
        render_to_response(
            os.path.join('tables/details', TEST_DETAILS_FILE),
            locals()).content)

  # Produce a performance landing page.
  tpl_perf_available = False
  if 'alerts' in dash_options:
    for alert in dash_options['alerts']:
      if ('platforms' in alert and
          {tpl_board: tpl_netbook} in alert['platforms']):
        tpl_perf_available = True
  dash_util.SaveHTML(
      os.path.join(base_dir, PERF_BUILDS_FILE),
      render_to_response(
          os.path.join('tables/details', PERF_BUILDS_FILE),
          locals()).content)


def _GetLandingDetails(dash_view, summary_ranges, netbook, board, category,
                       build):
  """Gather the summary details for one build (row).

  If the dashboard presented results from one source this
  would not be needed.  Since we grab data from test results,
  test attributes and crash summaries this sort of function
  is needed to collect distributed data for one build and category.

  Args:
    dash_view: data model with all test result details.
    summary_ranges: limits for data queries in this summary.
    netbook: netbook (e.g. netbook_MARIO_MP) for these pages.
    board: board (e.g. x86-mario) for these pages.
    category: summary producted for bvt now, maybe something else later.
    build: build to use.

  Returns:
    Tuple of data for populating one waterfall row (build).
  """
  job_attempted, job_good, passed, total, xpassed, xtotal = (
      dash_view.GetCategorySummary(netbook, board, category, build))
  kernel = summary_ranges.GetKernel(board, netbook, build)
  failed_tests = dash_view.GetCategoryFailedTests(
      netbook, board, category, build)
  if category == BVT_TAG:
    category = None
  crashes, crash_count, crash_category = (
      dash_view.GetCrashes().GetBuildCrashSummary(netbook, board, build,
                                                  category))
  # x86-alex-r18 -> x86-alex
  # x86-generic-full -> x86-generic-full
  release_index = board.rfind('-r')
  if release_index > 0:
    pure_board = board[:release_index]
  else:
    pure_board = board
  return (board, pure_board, netbook, build, job_attempted, job_good, passed,
          total, xpassed, xtotal, kernel, failed_tests, crashes, crash_count,
          crash_category)


def BuildLandingSummaries(dash_view, category, tots, branches, summary_ranges):
  """Produces individual table for each board of test summaries per build.

  This produces the data for the 'new-style' (waterfall) dashboard summary.

  Args:
    dash_view: data model with all test result details.
    category: summary producted for bvt now, maybe something else later.
    tots: boards to be grouped at the top of page.
    branches: boards to be grouped next.
    summary_ranges: limits for data queries in this summary.

  Returns:
    A dictionary with the data for the waterfall display.
  """
  platforms = []
  builds = {}
  build_info = BuildInfo()
  results_dict = {}
  releases = set()
  irregular_releases = set()

  for board in tots + branches:
    parsed_board, release = dash_view.ParseBoard(board)
    if release:
      releases.add(release)
    else:
      irregular_releases.add(board)
    for build_number in summary_ranges.GetBuildNumbers(board):
      build_results = results_dict.setdefault(build_number, {})
      for netbook in summary_ranges.GetNetbooks(board):
        # Aggregate the test summaries for each platform.
        platform = (parsed_board, netbook)
        if not platform in platforms:
          platforms.append(platform)
        if build_results.get(platform):
          logging.info('Multiple results for %s, %s', build_number, platform)
          continue
        build_results[platform] = _GetLandingDetails(
            dash_view, summary_ranges, netbook, board, category, build_number)
        # Keep track of earliest test job start time for each build.
        time_key = (netbook, board, category, build_number)
        start_time, _, _ = dash_view.GetJobTimesNone(*time_key)
        if not start_time:
          continue
        early_start = builds.setdefault(build_number, (start_time, time_key))
        if start_time < early_start[0]:
          builds[build_number] = (start_time, time_key)

  # Include the earliest job date among the platforms to be shown as the
  # overall 'release' (r15) test start date-time.
  organized_results = []
  for build, (start_time, time_key) in sorted(builds.iteritems(), reverse=True,
                                              key=lambda (k, v): v[0]):
    build_results = []
    for platform in platforms:
      build_results.append(results_dict.get(build, {}).get(platform))
    if time_key:
      formatted_start, _, _ = dash_view.GetFormattedJobTimes(*time_key)
    else:
      formatted_start = None
    if build[0].lower() == 'r':
      # R16-w.x.y format build number.
      build_release = build.split('-')[0][1:]
    else:
      # 0.15.x.y format build number.
      build_release = build.split('.')[1]
    organized_results.append((build, build_release,
                              formatted_start, build_results))

  return {'platforms': platforms,
          'irregular': irregular_releases,
          'releases': sorted(releases, reverse=True),
          'results': organized_results}


def BuildSummaryHTML(base_dir, html_filename, tpl_summary_data, last_updated):
  """Render actual page and save to an html file.

  Args:
    base_dir: base where resulting html file goes.
    html_filename: actual filename differs in views.
    tpl_summary_data: this data consumed by the template.
    last_updated: published on output pages.

  Render Variables:
    last_updated: date used by the template.
  """
  full_filepath = os.path.join(base_dir, html_filename)
  tpl_last_updated = last_updated

  dash_util.SaveHTML(
      full_filepath,
      render_to_response(
          os.path.join('tables/summary', html_filename), locals()).content)


def BuildAllTables(dash_base_dir, dash_view, dash_options, summary_limit,
                   waterfall_limit):
  """Build all detail pages and a few summary pages as well.

  Builds the detail pages for each netbook/board/category and then a
  waterfall-style summary and a few other summary pages.

  Args:
    dash_base_dir: base of dashboard output files.
    dash_view: data model with all test result details.
    dash_options: config options used for setting landing pages.
    summary_limit: only show n rows/table on the summary page.
    waterfall_limit: only show n rows on the waterfall summary page.

  Render Variables:
    last_updated: date used by the template.
  """
  tpl_last_updated = dash_view.GetFormattedLastUpdated()
  netbooks = dash_options.get('debug_netbook', dash_view.netbooks)
  for netbook in netbooks:
    for board_type in dash_view.GetNetbookBoardTypes(netbook):
      _BuildNetbookHTML(dash_base_dir, dash_view, netbook, board_type,
                        BVT_TAG, dash_options)

  for summary_file, build_fn, category, limit in (
      (TEST_WATERFALL_FILE, BuildLandingSummaries, BVT_TAG, waterfall_limit),
      (KERNEL_WATERFALL_FILE, BuildLandingSummaries, KERNELTEST_TAG,
       waterfall_limit)):

    summary_ranges = SummaryRanges(dash_view, category, limit)
    boards = summary_ranges.GetBoards()
    tots = []
    branches = []
    nonpriority = []
    for board in boards:
      if board in dash_options['priorityboards_tot']:
        tots.append(board)
      elif board in dash_options['priorityboards']:
        branches.append(board)
      else:
        nonpriority.append(board)
    branches += nonpriority

    BuildSummaryHTML(
        dash_base_dir,
        summary_file,
        build_fn(dash_view, category, tots, branches, summary_ranges),
        tpl_last_updated)

  dash_util.SaveHTML(
      os.path.join(dash_base_dir, TEST_LANDING_FILE),
      render_to_response(
          os.path.join('tables/summary', TEST_LANDING_FILE),
          locals()).content)
  dash_util.SaveHTML(
      os.path.join(dash_base_dir, EMAILS_SUMMARY_FILE),
      render_to_response(
          os.path.join('tables/summary', EMAILS_SUMMARY_FILE),
          locals()).content)


if __name__ == '__main__':
  print 'Run %s with --table-generate.' % DASHBOARD_MAIN
