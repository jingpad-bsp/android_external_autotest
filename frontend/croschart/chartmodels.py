# Copyright (c) 2011 The Chromium OS Authors. All rights reserved.
# Use of this source code is governed by a BSD-style license that can be
# found in the LICENSE file.

"""Django chart model implementation.

   Produce the data behind a google visualisation data table that can
   be rendered into a chart.

   This file is broken in 3 sections:
   1. Data queries wrapped in stateless function wrappers.
   2. Common helper functions to massage query results in to data tables.
   3. Data retrieval entry points that are called from views.

   Data entry points at this time include:
   -GetRangedOneKeyByBuildLinechartData(): produce a value by builds data table.
   -GetMultiTestKeyReleaseTableData(): produce a values by 2builds data table.
"""

import logging
import os
import re
import simplejson

from autotest_lib.frontend.afe import readonly_connection

from autotest_lib.frontend.croschart.charterrors import ChartDBError
from autotest_lib.frontend.croschart.charterrors import ChartInputError

import gviz_api


FIELD_SEPARATOR = ','
BUILD_PATTERN = re.compile(
    '([\w\-]+-r[c0-9]+)-([\d]+\.[\d]+\.[\d]+\.[\d]+)-(r[\w]{8})-(b[\d]+)')
COMMON_REGEXP = "'(%s).*'"
NO_DIFF = 'n/a'

###############################################################################
# Queries: These are designed as stateless functions with static relationships.
#          e.g. GetBuildRangedChartQuery() depends on
#               GetBaseQuery() for efficiency.
COMMON_QUERY_TEMPLATE = """
SELECT %(select_keys)s
FROM tko_perf_view_2
WHERE job_name REGEXP %(job_name)s
  AND platform = '%(platform)s'
  AND job_owner = 'chromeos-test'
  AND NOT ISNULL(iteration_value)
  AND iteration_value >= 0.0
  AND NOT ISNULL(test_started_time)
  AND NOT ISNULL(test_finished_time)
  AND NOT ISNULL(job_finished_time)"""

CHART_SELECT_KEYS = 'job_name, job_tag, iteration_value'
RELEASE_SELECT_KEYS = """
job_name, job_tag, test_name, iteration_key, iteration_value"""

CHART_QUERY_KEYS = """
  AND test_name = '%(test_name)s'
  AND iteration_key = '%(test_key)s'"""

RELEASEREPORT_QUERY_KEYS = """
  AND test_name in ('%(test_names)s')
  AND iteration_key in ('%(test_keys)s')"""

# Use subqueries to find bracketing dates mapping version to job_names.
RANGE_QUERY_TEMPLATE = """
AND test_started_time >= (%(min_query)s)
AND test_started_time <= (%(max_query)s)"""

# Can only get date order from the db.
DEFAULT_ORDER = 'ORDER BY test_started_time'
# Release data sorted here.
RELEASE_ORDER = ''


def GetBaseQueryParts(request):
  """Fully populates and returns a base query string."""
  query = COMMON_QUERY_TEMPLATE + CHART_QUERY_KEYS

  boards = '|'.join(request.GET.getlist('board'))
  platform = 'netbook_%s' % request.GET.get('system').upper()
  test_name, test_key = request.GET.get('testkey').split(FIELD_SEPARATOR)

  query_parameters = {}
  query_parameters['select_keys'] = CHART_SELECT_KEYS
  query_parameters['job_name'] = (COMMON_REGEXP % boards)
  query_parameters['platform'] = platform
  query_parameters['test_name'] = test_name
  query_parameters['test_key'] = test_key

  return query, query_parameters


def GetBaseQuery(request):
  """Produce the assembled query."""
  query, parameters = GetBaseQueryParts(request)
  return query % parameters


def GetBuildRangedChartQuery(request):
  """Apply a build range against the BaseQuery."""
  query = RANGE_QUERY_TEMPLATE

  boards = request.GET.getlist('board')
  from_build = request.GET.get('from_build')
  to_build = request.GET.get('to_build')

  base_query, base_query_parameters = GetBaseQueryParts(request)
  min_parameters = base_query_parameters.copy()
  min_parameters['select_keys'] = (
      'IFNULL(MIN(test_started_time), DATE_SUB(NOW(), INTERVAL 1 DAY))')
  min_parameters['job_name'] = (COMMON_REGEXP % '|'.join(
      '%s-%s' % (b, from_build.replace('.', '\.')) for b in boards))

  max_parameters = base_query_parameters
  max_parameters['select_keys'] = (
      'IFNULL(MAX(test_started_time), NOW())')
  max_parameters['job_name'] = (COMMON_REGEXP % '|'.join(
      '%s-%s' % (b, to_build.replace('.', '\.')) for b in boards))

  query_parameters = {}
  query_parameters['min_query'] = (base_query % min_parameters)
  query_parameters['max_query'] = (base_query % max_parameters)

  """Fully populates and returns a filter query string."""
  return query % query_parameters


def GetDateRangedChartQuery(request):
  """Apply a date range against the BaseQuery."""
  query = RANGE_QUERY_TEMPLATE

  from_date = request.GET.get('from_date')
  to_date = request.GET.get('to_date')

  query_parameters = {}
  query_parameters['min_query'] = "SELECT '%s'" % from_date
  query_parameters['max_query'] = "SELECT '%s'" % to_date

  """Fully populates and returns a filter query string."""
  return query % query_parameters


def GetIntervalRangedChartQuery(request):
  """Apply an interval range against the BaseQuery."""
  query = RANGE_QUERY_TEMPLATE

  interval = request.GET.get('interval')
  interval = interval.replace(FIELD_SEPARATOR, ' ')

  query_parameters = {}
  query_parameters['min_query'] = (
      'SELECT DATE_SUB(NOW(), INTERVAL %s)' % interval)
  query_parameters['max_query'] = 'SELECT NOW()'

  """Fully populates and returns a filter query string."""
  return query % query_parameters


def GetReleaseQueryParts(request):
  """Fully populates and returns a base query string."""
  query = COMMON_QUERY_TEMPLATE + RELEASEREPORT_QUERY_KEYS

  boards = request.GET.getlist('board')
  platform = 'netbook_%s' % request.GET.get('system').upper()
  test_names = set()
  test_keys = set()
  test_key_tuples = {}
  for t in request.GET.getlist('testkey'):
    test_key_tuples[t] = ''
  if not test_key_tuples:
    test_key_tuples = simplejson.load(open(os.path.join(
        os.path.abspath(os.path.dirname(__file__)),
        'crosrelease_defaults.json')))
  for t in test_key_tuples:
    test_name, test_key = t.split(FIELD_SEPARATOR)
    if not test_key:
      raise ChartInputError('testkey must be a test,key pair.')
    test_names.add(test_name)
    test_keys.add(test_key)

  from_build = request.GET.get('from_build')
  to_build = request.GET.get('to_build')

  query_parameters = {}
  query_parameters['select_keys'] = RELEASE_SELECT_KEYS
  query_parameters['job_name'] = "'(%s)-(%s|%s).*'" % (
      '|'.join(boards), from_build, to_build)
  query_parameters['platform'] = platform
  query_parameters['test_names'] = "','".join(test_names)
  query_parameters['test_keys'] = "','".join(test_keys)

  # Use the query_parameters to communicate parsed data.
  query_parameters['lowhigh'] = test_key_tuples

  return query, query_parameters


def GetReleaseQuery(request):
  """Produce the assembled query."""
  query, parameters = GetReleaseQueryParts(request)
  return query % parameters


###############################################################################
# Helpers
def AbbreviateBuild(build, with_board=False):
  """Condense full build string for x-axis representation."""
  m = re.match(BUILD_PATTERN, build)
  if not m or m.lastindex < 4:
    logging.warning('Skipping poorly formatted build: %s.', build)
    return build
  if with_board:
    new_build = '%s-%s-%s' % (m.group(1), m.group(2), m.group(4))
  else:
    new_build = '%s-%s' % (m.group(2), m.group(4))
  return new_build


def BuildNumberCmp(build_number1, build_number2):
  """Compare build numbers and return in ascending order."""
  # 3 different build formats:
  #1. xxx-yyy-r13-0.12.133.0-b1
  #2. ttt_sss-rc-0.12.133.0-b1
  #3. 0.12.133.0-b1
  build1_split = build_number1.split('-')
  build2_split = build_number2.split('-')
  if len(build1_split) > 5:
    return cmp(build_number1, build_number2)
  if len(build1_split) > 3:
    if len(build1_split) == 4:
      board1, release1, build1, b1 = build1_split
      board2, release2, build2, b2 = build2_split
      platform1 = platform2 = ''
    else:
      platform1, board1, release1, build1, b1 = build1_split
      platform2, board2, release2, build2, b2 = build2_split

    if (platform1, board1, release1) != (platform2, board2, release2):
      if platform1 != platform2:
        return cmp(platform1, platform2)
      if board1 != board2:
        return cmp(board1, board2)
      if release1 != release2:
        return cmp(int(release1[1:]), int(release2[1:]))
  else:
    build1, b1 = build1_split
    build2, b2 = build2_split

  if build1 != build2:
    major1 = build1.split('.')
    major2 = build2.split('.')
    major_len = min([len(major1), len(major2)])
    for i in xrange(major_len):
      if major1[i] != major2[i]:
        return cmp(int(major1[i]), int(major2[i]))
    return cmp(build1, build2)
  else:
    return cmp(int(b1[1:]), int(b2[1:]))


###############################################################################
# Models
def GetOneKeyByBuildLinechartData(test_key, query, query_order=DEFAULT_ORDER):
  """Prepare and run the db query and massage the results."""

  def AggregateBuilds(test_key, data_list):
    """Groups and averages data by build and extracts job_tags."""
    raw_dict = {}  # unsummarized data
    builds_inorder = []  # summarized data
    job_tags = []  # for click-through to data
    # Organize the returned data by build.
    # Keep the builds in date order and check build name format.
    for build, tag, test_value in data_list:
      build = AbbreviateBuild(build)
      if not build in raw_dict:
        builds_inorder.append({'build': build})
        job_tags.append(tag)
      value_list = raw_dict.setdefault(build, [])
      value_list.append(test_value)
    if not builds_inorder:
      raise ChartDBError('No data returned')
    # Now avg data by build and key. This is the format used by gviz.
    for build_dict in builds_inorder:
      value_list = raw_dict[build_dict['build']]
      build_dict[test_key] = round(sum(value_list, 0.0) / len(value_list), 2)
    return job_tags, builds_inorder

  def ToGVizJsonTable(test_key, builds_inorder):
    """Massage data into gviz data table in proper order."""
    # Now format for gviz table.
    gviz_data_table = gviz_api.DataTable({'build': ('string', 'Build'),
                                          test_key: ('number', test_key)})
    gviz_data_table.LoadData(builds_inorder)
    gviz_data_table = gviz_data_table.ToJSon(['build', test_key])
    return gviz_data_table

  # Now massage the returned data into a gviz data table.
  cursor = readonly_connection.connection().cursor()
  cursor.execute('%s %s' % (query, query_order))
  job_tags, build_data = AggregateBuilds(test_key, cursor.fetchall())
  gviz_data_table = ToGVizJsonTable(test_key, build_data)
  return {'gviz_data_table': gviz_data_table, 'job_tags': job_tags}


def GetRangedOneKeyByBuildLinechartData(request):
  """Assemble the proper query and order."""

  ranged_queries = {'from_build': GetBuildRangedChartQuery,
                    'from_date': GetDateRangedChartQuery,
                    'interval': GetIntervalRangedChartQuery}

  query_list = [GetBaseQuery(request)]
  for range_key in ['from_build', 'from_date', 'interval', None]:
    if request.GET.get(range_key, None):
      break
  if not range_key:
    raise ChartInputError('One interval-type parameter must be supplied.')
  query_list.append(ranged_queries[range_key](request))
  test_name, test_key = request.GET.get('testkey').split(FIELD_SEPARATOR)
  data_dict = GetOneKeyByBuildLinechartData(test_key, ' '.join(query_list))
  # Added for chart labeling.
  data_dict.update({'test_name': test_name, 'test_key': test_key})
  return data_dict


def GetMultiTestKeyReleaseTableData(query, query_order=RELEASE_ORDER,
                                    extra=None):
  """Prepare and run the db query and massage the results."""

  def GetHighlights(test_name, test_key, lowhigh, diff):
    """Select the background color based on a setting and the diff value."""
    black_fg = '#000000'
    green_fg = '#009900'
    red_fg = '#cc0000'
    highlights = {'test': test_name, 'metric': test_key, 'diff': diff}

    if not lowhigh:
      # Cannot decide which indicators to show.
      return highlights

    # Lookup if this key is driven up or down.
    image_template = '<img src="/images/%s" />'
    lowhigh_indicator = {'lowisgood': image_template % 'downisgoodmetric.png',
                         'highisgood': image_template % 'upisgoodmetric.png'}
    lookup = lowhigh.get('%s,%s' % (test_name, test_key), None)
    if not lookup or not lookup in lowhigh_indicator:
      # Cannot get a key indicator or diff indicator.
      return highlights

    highlights['metric'] = '%s%s' % (test_key, lowhigh_indicator[lookup])
    if diff == NO_DIFF:
      # Cannot pick a diff indicator.
      return highlights

    image_vector = [(red_fg, image_template % 'unhappymetric.png'),
                    (black_fg, ''),
                    (green_fg, image_template % 'happymetric.png')]
    media_lookup = {'lowisgood': image_vector,
                    'highisgood': image_vector[::-1]}
    cmp_diff = float(diff.split(' ')[0])
    fg_color, diff_indicator = media_lookup[lookup][cmp(cmp_diff, 0.0)+1]
    diff_template = '<span style="color:%s">%s%s</span>'
    highlights['diff'] = diff_template % (fg_color, diff, diff_indicator)
    return highlights


  def CalculateDiff(diff_list):
    """Produce a diff string."""
    if len(diff_list) < 2:
      return NO_DIFF
    return '%s (%s%%)' % (
        diff_list[0] - diff_list[1],
        round((diff_list[0] - diff_list[1]) / diff_list[0] * 100))

  def AggregateBuilds(lowhigh, data_list):
    """Groups and averages data by build and extracts job_tags."""
    raw_dict = {}  # unsummarized data
    builds = set()
    # Aggregate all the data values by test_name, test_key, build.
    for build, tag, test_name, test_key, test_value in data_list:
      key_dict = raw_dict.setdefault(test_name, {})
      build_dict = key_dict.setdefault(test_key, {})
      build = AbbreviateBuild(build=build, with_board=True)
      job_dict = build_dict.setdefault(build, {})
      job_dict.setdefault('tag', tag)
      value_list = job_dict.setdefault('values', [])
      value_list.append(test_value)
      builds.add(build)
    if not raw_dict:
      raise ChartDBError('No data returned')
    if len(builds) < 2:
      raise ChartDBError(
          'Release report expected 2 builds and found %s builds.' % len(builds))
    # Now append summary dict entries of the data for gviz.
    builds = sorted(builds, cmp=BuildNumberCmp)
    build_data = []
    for test_name, key_dict in raw_dict.iteritems():
      for test_key, build_dict in key_dict.iteritems():
        data_dict = {}
        diff_stats = []
        for build in builds:
          job_dict = build_dict.get(build, None)
          # Need to make sure there is a value for every build.
          if job_dict:
            value_list = job_dict['values']
            avg = round(sum(value_list, 0.0) / len(value_list), 2)
            diff_stats.append(avg)
            data_dict[build] = (
                '<a href="http://cautotest/results/%s/%s/results/keyval" '
                'target="_blank">%s</a>' % (job_dict['tag'], test_name, avg))
          else:
            data_dict[build] = 0.0
        diff = CalculateDiff(diff_stats)
        data_dict.update(GetHighlights(test_name, test_key, lowhigh, diff))
        build_data.append(data_dict)
    return builds, build_data

  def ToGVizJsonTable(builds, table_data):
    """Massage data into gviz data table in proper order."""
    # Now format for gviz table.
    description = {'test': ('string', 'Test'),
                   'metric': ('string', 'Metric'),
                   'diff': ('string', 'Diff')}
    keys_in_order = ['test', 'metric']
    for build in builds:
      description[build] = ('string', build)
      keys_in_order.append(build)
    keys_in_order.append('diff')
    gviz_data_table = gviz_api.DataTable(description)
    gviz_data_table.LoadData(table_data)
    gviz_data_table = gviz_data_table.ToJSon(keys_in_order)
    return gviz_data_table

  # Now massage the returned data into a gviz data table.
  cursor = readonly_connection.connection().cursor()
  cursor.execute('%s %s' % (query, query_order))
  builds, build_data = AggregateBuilds(lowhigh=extra.get('lowhigh', None),
                                       data_list=cursor.fetchall())
  gviz_data_table = ToGVizJsonTable(builds, build_data)
  return {'gviz_data_table': gviz_data_table}


def GetReleaseReportData(request):
  """Prepare and run the db query and massage the results."""

  query, parameters = GetReleaseQueryParts(request)
  data_dict = GetMultiTestKeyReleaseTableData(
      query=query % parameters, extra=parameters)
  return data_dict
