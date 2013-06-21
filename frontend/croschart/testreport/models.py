# Copyright (c) 2012 The Chromium OS Authors. All rights reserved.
# Use of this source code is governed by a BSD-style license that can be
# found in the LICENSE file.
# pylint: disable-msg=C0111

"""Django chart models for a report listing all known automated tests.

   Produce the data behind a google visualisation data table that can
   be rendered into a chart.

   Data entry points at this time include:
   -GetRangedTestReportData(): produce a tests by #executed data table.
"""

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
TEST_QUERY_TEMPLATE = """
SELECT * FROM
(SELECT name as test_name, test_class, test_type, path, author, test_category,
       '' as platform, 0 as run_count, 0.0 as avg_test_time
FROM afe_autotests
  %(afe_where)s
UNION
SELECT test_name, '' as test_class, '' as test_type, '' as path, '' as author,
       '' as test_category, platform, COUNT(*) as run_count,
       ROUND(AVG(TIME_TO_SEC(TIMEDIFF(test_finished_time, test_started_time))))
       as avg_test_time
FROM tko_test_view_2
WHERE NOT test_name REGEXP '(CLIENT|SERVER)_JOB.*'
  AND NOT test_name REGEXP 'boot\.[0-9]'
  AND NOT ISNULL(test_started_time)
  AND NOT ISNULL(test_finished_time)
  %(tko_where)s
GROUP BY test_name, subdir, platform) AS q"""


def GetBaseTestQuery(request):
  """Test query is simple with no parameters."""
  query = TEST_QUERY_TEMPLATE
  return query


###############################################################################
# Models
def GetTestReportData(query):
  """Prepare and run the db query and massage the results."""

  def AggregateTests(data_list):
    """Groups multiple row data by test name and platform."""
    raw_dict = {}
    test_attributes = set()
    platform_attributes = set()
    for (test_name, test_class, test_type, path, author, test_category,
         platform, run_count, avg_test_time) in data_list:
      if test_name.find(':') > -1:
        continue
      test_dict = raw_dict.setdefault(test_name, {'test_name': test_name,
                                                  'run_count': 0})
      for field_name, field in (('test_class', test_class),
                                ('test_type', test_type),
                                ('path', path),
                                ('author', author),
                                ('test_category', test_category)):
        if field:
          test_dict.setdefault(field_name, field)
          test_attributes.add(field_name)
      if platform:
        platform_name = platform[8:]
        if run_count:
          test_dict['run_count'] += int(run_count)
          field_name = '%s-run_count' % platform_name
          test_dict.setdefault(field_name, run_count)
          platform_attributes.add(field_name)
        if avg_test_time:
          field_name = '%s-avg_test_time' % platform_name
          test_dict.setdefault(field_name, avg_test_time)
          platform_attributes.add(field_name)
    if not raw_dict:
      raise ChartDBError('No data returned')
    return (raw_dict.values(),
            sorted(list(test_attributes)) + sorted(list(platform_attributes)))

  def ToGVizJsonTable(table_data, test_attributes):
    """Massage data into gviz data table in proper order."""
    # Now format for gviz table.
    description = {'test_name': ('string', 'Name'),
                   'run_count': ('number', '#Run')}
    keys_in_order = ['test_name', 'run_count']
    for a in test_attributes:
      description[a] = ('string', a)
      keys_in_order.append(a)
    gviz_data_table = gviz_api.DataTable(description)
    gviz_data_table.LoadData(table_data)
    gviz_data_table = gviz_data_table.ToJSon(keys_in_order)
    return gviz_data_table

  cursor = readonly_connection.connection().cursor()
  cursor.execute(query)
  test_data, test_attributes = AggregateTests(cursor.fetchall())
  gviz_data_table = ToGVizJsonTable(test_data, test_attributes)
  return {'gviz_data_table': gviz_data_table}


def AddWhereClause(existing, new_clause):
  """Add a clause to a SQL WHERE."""
  if not existing or not existing.strip():
    return ' WHERE %s ' % new_clause
  else:
    return existing + (' AND %s ' % new_clause)


def GetRangedTestReportData(request):
  """Prepare and run the db query and massage the results."""
  ranged_queries = {'from_date': chartmodels.GetDateRangedChartQuery,
                    'interval': chartmodels.GetIntervalRangedChartQuery}
  for range_key in ['from_date', 'interval', None]:
    if request.GET.get(range_key, None):
      break
  if not range_key:
    raise ChartInputError('One interval-type parameter must be supplied.')
  query_parameters = {'afe_where': ' ',
                      'tko_where': ranged_queries[range_key](request)}
  test_name = request.GET.get('test_name')
  if test_name and test_name.strip():
    query_parameters['afe_where'] = AddWhereClause(
        query_parameters['afe_where'], "name = '%s'" % test_name.strip())
    query_parameters['tko_where'] = AddWhereClause(
        query_parameters['tko_where'], "test_name = '%s'" % test_name.strip())
  query = GetBaseTestQuery(request) % query_parameters
  if request.GET.get('query'):
    raise ChartDBError(query)
  data_dict = GetTestReportData(query)
  return data_dict
