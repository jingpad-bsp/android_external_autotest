# Copyright (c) 2011 The Chromium OS Authors. All rights reserved.
# Use of this source code is governed by a BSD-style license that can be
# found in the LICENSE file.
# pylint: disable-msg=C0111

"""Django chart models for a report listing all known automated tests.

   Produce the data behind a google visualisation data table that can
   be rendered into a chart.

   Data entry points at this time include:
   -GetMultiTestKeyReleaseTableData(): produce a values by builds data table.
   -GetReleaseReportData(): produce perf stats comparison data table.
"""

import json
import os

from autotest_lib.frontend.afe import readonly_connection

import autotest_lib.frontend.croschart.chartmodels as chartmodels
import autotest_lib.frontend.croschart.chartutils as chartutils

from autotest_lib.frontend.croschart.charterrors import ChartDBError
from autotest_lib.frontend.croschart.charterrors import ChartInputError

try:
    import gviz_api
except ImportError:
    # Do nothing, in case this is part of a unit test.
    pass

NO_DIFF = 'n/a'


###############################################################################
# Queries: These are designed as stateless functions with static relationships.
#          e.g. GetBuildRangedChartQuery() depends on
#               GetBasePerfQuery() for efficiency.
RELEASE_SELECT_KEYS = """
job_name, job_tag, test_name, iteration_key, iteration_value"""

RELEASEREPORT_QUERY_KEYS = """
  AND test_name in ('%(test_names)s')
  AND iteration_key in ('%(test_keys)s')"""

# Release data sorted here.
RELEASE_ORDER = ''


def GetReleaseQueryParts(request):
  """Fully populates and returns a base query string."""
  query = chartmodels.COMMON_PERF_QUERY_TEMPLATE + RELEASEREPORT_QUERY_KEYS

  boards = request.GET.getlist('board')
  platform = '%s' % request.GET.get('system').upper()
  test_names = set()
  test_keys = set()
  test_key_tuples = {}
  for t in request.GET.getlist('testkey'):
    test_key_tuples[t] = ''
  if not test_key_tuples:
    test_key_tuples = json.load(open(os.path.join(
        os.path.abspath(os.path.dirname(__file__)),
        'crosrelease_defaults.json')))
  for t in test_key_tuples:
    test_name, test_key = chartutils.GetTestNameKeys(t)
    if not test_key or len(test_key) > 1:
      raise ChartInputError('testkey must be a test,key pair.')
    test_names.add(test_name)
    test_keys.add(test_key[0])

  from_build = request.GET.get('from_build')
  to_build = request.GET.get('to_build')

  query_parameters = {}
  query_parameters['select_keys'] = RELEASE_SELECT_KEYS
  query_parameters['job_name'] = "'(%s)-(%s|%s)-.*'" % (
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
def BuildNumberCmp(build_number1, build_number2):
  """Compare build numbers and return in ascending order."""
  # 10 different build patterns:
  #1. xxx-yyy-r13 0.12.133.0-b1 [(chrome version)]
  #2. ttt_sss1100-rc 0.12.133.0-b1 [(chrome version)]
  #3. 0.12.133.0-b1 [(chrome version)]
  #4. xxx-yyy-r13 R16-1131.0.0-b1 [(chrome version)]
  #5. ttt_sss-rc R16-1131.0.0-b1 [(chrome version)]

  def GetPureBuild(build):
    """This code coordinated with AbbreviateBuild()."""
    divided = build.split('(')[0].strip().split(chartutils.BUILD_PART_SEPARATOR)
    dlen = len(divided)
    if dlen > 2:
      raise ChartDBError('Unexpected build format: %s' % build)
    # Get only the w.x.y.z part.
    dehyphened = divided[dlen-1].split('-')
    if len(dehyphened) == 3 and dehyphened[0][0] == 'R':
      return '%s.%s' % (dehyphened[0][1:], dehyphened[1]), dehyphened[2]
    return dehyphened

  build1, b1 = GetPureBuild(build_number1)
  build2, b2 = GetPureBuild(build_number2)

  if build1 != build2:
    # Compare each part of the build.
    major1 = build1.split('.')
    major2 = build2.split('.')
    major_len = min([len(major1), len(major2)])
    for i in xrange(major_len):
      if major1[i] != major2[i]:
        return cmp(int(major1[i]), int(major2[i]))
    return cmp(build1, build2)
  else:
    # Compare the buildbot sequence numbers only.
    return cmp(int(b1[1:]), int(b2[1:]))


###############################################################################
# Models
def GetMultiTestKeyReleaseTableData(chrome_versions, query,
                                    query_order=RELEASE_ORDER, extra=None):
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

  def AggregateBuilds(lowhigh, chrome_versions, data_list):
    """Groups and averages data by build and extracts job_tags."""
    # Aggregate all the data values.
    # raw_dict
    #   test_name
    #     test_key
    #       build
    #         'tag'
    #         'values'
    raw_dict = {}  # unsummarized data
    builds = set()
    for build, tag, test_name, test_key, test_value in data_list:
      key_dict = raw_dict.setdefault(test_name, {})
      build_dict = key_dict.setdefault(test_key, {})
      build = chartutils.AbbreviateBuild(build, chrome_versions,
                                         with_board=True)
      if not build:
        continue
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
    # Now calculate averages, diff and acquire indicators.
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
  builds, build_data = AggregateBuilds(extra.get('lowhigh', None),
                                       chrome_versions,
                                       data_list=cursor.fetchall())
  gviz_data_table = ToGVizJsonTable(builds, build_data)
  return {'gviz_data_table': gviz_data_table}


def GetReleaseReportData(request):
  """Prepare and run the db query and massage the results."""

  query, parameters = GetReleaseQueryParts(request)
  chrome_versions = chartutils.GetChromeVersions(request)
  data_dict = GetMultiTestKeyReleaseTableData(chrome_versions,
      query=query % parameters, extra=parameters)
  return data_dict
