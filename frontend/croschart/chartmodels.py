# Copyright (c) 2011 The Chromium OS Authors. All rights reserved.
# Use of this source code is governed by a BSD-style license that can be
# found in the LICENSE file.

"""Django chart model implementation.

   This class produces the data behind a google visualisation data table
   that can be rendered into a chart.

   CLASSES:

   BaseChartQuery: building block class.
   |->BuildRangedChartQuery: adds from_build/to_build constraint.
   |->DateRangedChartQuery: adds from_date/to_date constraint.
   |->IntervalRangedChartQuery: adds mysql interval constraint.

   OneKeyByBuildLinechart: base chart building model class.
   |->OneKeyRangedChartModel: adds from_build/to_build constraint.

   FUNCTIONS:

   GetChartData(): The principal entry-point.
"""

import logging
import re

from autotest_lib.frontend.afe import readonly_connection

from autotest_lib.frontend.croschart.charterrors import ChartDBError
from autotest_lib.frontend.croschart.charterrors import ChartInputError

import gviz_api


FIELD_SEPARATOR = ','
BUILD_PATTERN = re.compile(
    '[\w]+\-[\w]+\-r[\w]+\-'
    '([\d]+\.[\d]+\.[\d]+\.[\d]+)-(r[\w]{8})-(b[\d]+)')
COMMON_REGEXP = "'(%s).*'"

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

CHART_QUERY_KEYS = """
  AND test_name = '%(test_name)s'
  AND iteration_key = '%(test_key)s'"""

# Use subqueries to find bracketing dates mapping version to job_names.
RANGE_QUERY_TEMPLATE = """
AND test_started_time >= (%(min_query)s)
AND test_started_time <= (%(max_query)s)"""

DEFAULT_ORDER = 'ORDER BY test_started_time'


def GetBaseQuery(request, raw=False):
  """Fully populates and returns a base query string."""
  query = COMMON_QUERY_TEMPLATE + CHART_QUERY_KEYS

  boards = '|'.join(request.GET.getlist('board'))
  platform = 'netbook_%s' % request.GET.get('system').upper()
  test_name, test_key = request.GET.get('testkey').split(FIELD_SEPARATOR)

  query_parameters = {}
  query_parameters['select_keys'] = 'job_name, job_tag, iteration_value'
  query_parameters['job_name'] = (COMMON_REGEXP % boards)
  query_parameters['platform'] = platform
  query_parameters['test_name'] = test_name
  query_parameters['test_key'] = test_key

  if raw:
    return query, query_parameters
  else:
    return query % query_parameters


def GetBuildRangedChartQuery(request):
  """Apply a build range against the BaseQuery."""
  query = RANGE_QUERY_TEMPLATE

  boards = request.GET.getlist('board')
  from_build = request.GET.get('from_build')
  to_build = request.GET.get('to_build')

  base_query, base_query_parameters = GetBaseQuery(request, raw=True)
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


###############################################################################
# Helpers
def AbbreviateBuild(build):
  """Condense full build string for x-axis representation."""
  m = re.match(BUILD_PATTERN, build)
  if not m:
    logging.warning('Skipping poorly formatted build: %s.', build)
    return build
  new_build = '%s-%s' % (m.group(1), m.group(3))
  return new_build


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
