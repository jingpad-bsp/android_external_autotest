# Copyright (c) 2011 The Chromium OS Authors. All rights reserved.
# Use of this source code is governed by a BSD-style license that can be
# found in the LICENSE file.
# pylint: disable-msg=C0111

"""Django chart models for labtest report.

   Produce the data behind a google visualisation data table that can
   be rendered into a chart.

   Data entry points at this time include:
   -GetRangedLabTestReportData(): produce labtest execution data table.
"""

import json
import os

from autotest_lib.frontend.afe import readonly_connection

import autotest_lib.frontend.croschart.chartmodels as chartmodels
from autotest_lib.frontend.croschart.charterrors import ChartDBError
from autotest_lib.frontend.croschart.charterrors import ChartInputError

try:
    import gviz_api
except ImportError:
    # Do nothing, in case this is part of a unit test.
    pass

###############################################################################
# Queries: These are designed as stateless functions with static relationships.
#          e.g. GetBuildRangedChartQuery() depends on
#               GetBasePerfQuery() for efficiency.
LABTEST_QUERY_TEMPLATE = """
SELECT job_name, job_owner,
       STR_TO_DATE(CONCAT(YEARWEEK(test_started_time), ' Sunday'), '%%X%%V %%W'),
       COUNT(*) AS test_count
FROM tko_test_view_2
WHERE job_owner != 'chromeos-test'
  AND NOT test_name REGEXP '(CLIENT|SERVER)_JOB.*'
  AND NOT test_name REGEXP 'boot\.[0-9]'
  AND NOT ISNULL(test_started_time)
  AND NOT ISNULL(test_finished_time)
  AND job_owner = LEFT(job_name, LENGTH(job_owner))
  %s
GROUP BY job_name, job_owner, YEARWEEK(test_started_time)"""


def GetBaseLabTestQuery(request):
  """Test query is simple with no parameters."""
  query = LABTEST_QUERY_TEMPLATE
  return query


###############################################################################
# Helpers
def GetKernelTeam():
  """Get Kernel team if requested."""
  kernel_team = None
  team_file = os.path.join(os.path.abspath(os.path.dirname(__file__)),
                          'kernel-team.json')
  if os.path.exists(team_file):
    kernel_team = json.load(open(team_file))
  return kernel_team


###############################################################################
# Models
def GetLabTestReportData(query):
  """Prepare and run the db query and massage the results."""

  def AggregateTests(data_list):
    """Groups multiple row data by test name and platform."""
    raw_data = []
    user_data = {}
    for job_name, job_owner, week_date, test_count in data_list:
      raw_data.append({'job_name': job_name,
                       'job_owner': job_owner,
                       'week_date': week_date,
                       'test_count': test_count})
      if not job_owner in user_data:
        user_data[job_owner] = {'job_owner': job_owner,
                                'test_count': test_count}
      else:
        user_data[job_owner]['test_count'] += test_count
    if not raw_data:
      raise ChartDBError('No data returned')
    # Add zero-values for members not found.
    kernel_team = GetKernelTeam()
    if kernel_team:
      for k in kernel_team:
        if not k in user_data:
          user_data[k] = {'job_owner': k, 'test_count': 0}
    return raw_data, sorted(user_data.values())

  def ToGVizJsonTable(table_data, user_table_data):
    """Massage data into gviz data table in proper order."""
    # Now format for gviz tables: jobs and users.
    description = {'job_name': ('string', 'Job'),
                   'job_owner': ('string', 'Owner'),
                   'week_date': ('string', 'Week'),
                   'test_count': ('number', '#Tests')}
    keys_in_order = ['job_name', 'job_owner', 'week_date', 'test_count']
    gviz_data_table_jobs = gviz_api.DataTable(description)
    gviz_data_table_jobs.LoadData(table_data)
    gviz_data_table_jobs = gviz_data_table_jobs.ToJSon(keys_in_order)

    description = {'job_owner': ('string', 'Owner'),
                   'test_count': ('number', '#Tests')}
    keys_in_order = ['job_owner', 'test_count']
    gviz_data_table_users = gviz_api.DataTable(description)
    gviz_data_table_users.LoadData(user_table_data)
    gviz_data_table_users = gviz_data_table_users.ToJSon(keys_in_order)
    return {'jobs': gviz_data_table_jobs, 'users': gviz_data_table_users}

  cursor = readonly_connection.cursor()
  cursor.execute(query)
  test_data, user_data = AggregateTests(cursor.fetchall())
  gviz_data_table = ToGVizJsonTable(test_data, user_data)
  return {'gviz_data_table': gviz_data_table}


def GetRangedLabTestReportData(request):
  """Prepare and run the db query and massage the results."""
  ranged_queries = {'from_date': chartmodels.GetDateRangedChartQuery,
                    'interval': chartmodels.GetIntervalRangedChartQuery}
  for range_key in ['from_date', 'interval', None]:
    if request.GET.get(range_key, None):
      break
  if not range_key:
    raise ChartInputError('One interval-type parameter must be supplied.')
  query = GetBaseLabTestQuery(request) % (ranged_queries[range_key](request))
  data_dict = GetLabTestReportData(query)
  return data_dict
