# Copyright (c) 2012 The Chromium OS Authors. All rights reserved.
# Use of this source code is governed by a BSD-style license that can be
# found in the LICENSE file.

"""Django chart model implementation.

   Produce the data behind a google visualisation data table that can
   be rendered into a chart.
"""

import autotest_lib.frontend.croschart.chartutils as chartutils


COMMON_REGEXP = "'(%s).*'"


###############################################################################
# Queries: These are designed as stateless functions with static relationships.
#          e.g. GetBuildRangedChartQuery() depends on
#               GetBasePerfQuery() for efficiency.
PLATFORM_QUERY_TEMPLATE = """
  AND platform REGEXP '(desktop|netbook)_%(platform)s'"""

COMMON_PERF_QUERY_TEMPLATE = """
SELECT %(select_keys)s
FROM tko_perf_view_2
WHERE job_name REGEXP %(job_name)s
  AND job_owner = 'chromeos-test'
  AND NOT ISNULL(iteration_value)
  AND iteration_value >= 0.0
  AND NOT ISNULL(test_started_time)
  AND NOT ISNULL(test_finished_time)
  AND NOT ISNULL(job_finished_time)""" + PLATFORM_QUERY_TEMPLATE

CHART_SELECT_KEYS = 'job_name, job_tag, iteration_key, iteration_value'

CHART_QUERY_KEYS = """
  AND test_name = '%(test_name)s'
  AND iteration_key in ('%(test_keys)s')"""

# Use subqueries to find bracketing dates mapping version to job_names.
RANGE_QUERY_TEMPLATE = """
AND test_started_time >= (%(min_query)s)
AND test_started_time <= (%(max_query)s)"""


def GetBasePerfQueryParts(request):
  """Fully populates and returns a base query string."""
  query = COMMON_PERF_QUERY_TEMPLATE + CHART_QUERY_KEYS

  boards = '|'.join(request.GET.getlist('board'))
  platform = request.GET.get('system').upper()
  test_name, test_keys = chartutils.GetTestNameKeys(request.GET.get('testkey'))

  query_parameters = {}
  query_parameters['select_keys'] = CHART_SELECT_KEYS
  query_parameters['job_name'] = (COMMON_REGEXP % boards)
  query_parameters['platform'] = platform
  query_parameters['test_name'] = test_name
  query_parameters['test_keys'] = "','".join(test_keys)

  return query, query_parameters


def GetBasePerfQuery(request):
  """Produce the assembled query."""
  query, parameters = GetBasePerfQueryParts(request)
  return query % parameters


def GetBuildRangedChartQuery(request):
  """Apply a build range against the BaseQuery."""
  query = RANGE_QUERY_TEMPLATE

  boards = request.GET.getlist('board')
  from_build = request.GET.get('from_build')
  to_build = request.GET.get('to_build')

  base_query, base_query_parameters = GetBasePerfQueryParts(request)
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


def GetPlatformChartQuery(request):
  """Handle an optional system query parameter."""
  query_parameters = {}
  platform = request.GET.get('system')
  if platform and platform.strip():
    query_parameters['platform'] = platform.strip().upper()
    return PLATFORM_QUERY_TEMPLATE % query_parameters
  return ' '


def GetDateRangedChartQuery(request):
  """Apply a date range against the BaseQuery."""
  query = RANGE_QUERY_TEMPLATE

  from_date = request.GET.get('from_date')
  to_date = request.GET.get('to_date')

  query_parameters = {}
  query_parameters['min_query'] = "SELECT '%s'" % from_date
  query_parameters['max_query'] = "SELECT '%s'" % to_date

  """Fully populates and returns a filter query string."""
  return query % query_parameters + GetPlatformChartQuery(request)


def GetIntervalRangedChartQuery(request):
  """Apply an interval range against the BaseQuery."""
  query = RANGE_QUERY_TEMPLATE

  interval = request.GET.get('interval')
  interval = interval.replace(chartutils.FIELD_SEPARATOR, ' ')

  query_parameters = {}
  query_parameters['min_query'] = (
      'SELECT DATE_SUB(NOW(), INTERVAL %s)' % interval)
  query_parameters['max_query'] = 'SELECT NOW()'

  """Fully populates and returns a filter query string."""
  return query % query_parameters + GetPlatformChartQuery(request)
