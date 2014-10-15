# Copyright (c) 2011 The Chromium OS Authors. All rights reserved.
# Use of this source code is governed by a BSD-style license that can be
# found in the LICENSE file.
# pylint: disable-msg=C0111

"""Django chart models for performance key-build charts.

   Produce the data behind a google visualisation data table that can
   be rendered into a chart.

   Data entry points at this time include:
   -GetRangedKeyByBuildLinechartData(): produce a value by builds data table.
"""

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

# Can only get date order from the db.
DEFAULT_ORDER = 'ORDER BY test_started_time'

# Narrow data to a set of known machines.
HOSTNAME_QUERY_TEMPLATE = "AND hostname in ('%s')"


###############################################################################
# Models
def GetKeysByBuildLinechartData(test_name, test_keys, chrome_versions, query,
                                query_order=DEFAULT_ORDER):
  """Prepare and run the db query and massage the results."""

  def AggregateBuilds(test_keys, chrome_versions, data_list):
    """Groups and averages data by build and extracts job_tags."""
    # raw_dict
    #   build
    #     test_key: values
    raw_dict = {}  # unsummarized data
    builds_inorder = []  # summarized data
    job_tags = []

    # Aggregate all the data values by test_name, test_key, build.
    for build, tag, test_key, test_value in data_list:
      build = chartutils.AbbreviateBuild(build, chrome_versions)
      if not build:
        continue
      if not build in raw_dict:
        builds_inorder.append({'build': build})
        job_tags.append(tag)
      key_dict = raw_dict.setdefault(build, {})
      value_list = key_dict.setdefault(test_key, [])
      value_list.append(test_value)
    if not raw_dict:
      raise ChartDBError('No data returned')
    # Now calculate averages.
    for data_dict in builds_inorder:
      build_dict = raw_dict[data_dict['build']]
      for test_key, value_list in build_dict.iteritems():
        avg = round(sum(value_list, 0.0) / len(value_list), 2)
        data_dict[test_key] = avg
    return job_tags, builds_inorder

  def ToGVizJsonTable(test_keys, new_test_keys, table_data):
    """Massage data into gviz data table in proper order."""
    # Now format for gviz table.
    description = {'build': ('string', 'Build')}
    keys_in_order = ['build']
    for i in xrange(len(test_keys)):
      description[test_keys[i]] = ('number', new_test_keys[i])
      keys_in_order.append(test_keys[i])
    gviz_data_table = gviz_api.DataTable(description)
    gviz_data_table.LoadData(table_data)
    gviz_data_table = gviz_data_table.ToJSon(keys_in_order)
    return gviz_data_table

  cursor = readonly_connection.cursor()
  cursor.execute('%s %s' % (query, query_order))
  job_tags, build_data = AggregateBuilds(test_keys, chrome_versions,
                                         cursor.fetchall())
  new_test_name, new_test_keys = chartutils.AbridgeCommonKeyPrefix(test_name,
                                                                   test_keys)
  gviz_data_table = ToGVizJsonTable(test_keys, new_test_keys, build_data)
  return {'test_name': test_name, 'test_keys': new_test_keys,
          'chart_title': new_test_name, 'gviz_data_table': gviz_data_table,
          'job_tags': job_tags}


def GetRangedKeyByBuildLinechartData(request):
  """Assemble the proper query and order."""
  ranged_queries = {'from_build': chartmodels.GetBuildRangedChartQuery,
                    'from_date': chartmodels.GetDateRangedChartQuery,
                    'interval': chartmodels.GetIntervalRangedChartQuery}
  query_list = [chartmodels.GetBasePerfQuery(request)]
  for range_key in ['from_build', 'from_date', 'interval', None]:
    if request.GET.get(range_key, None):
      break
  if not range_key:
    raise ChartInputError('One interval-type parameter must be supplied.')
  query_list.append(ranged_queries[range_key](request))
  chrome_versions = chartutils.GetChromeVersions(request)
  host_names = request.GET.get('hostnames')
  if host_names:
    query_list.append(HOSTNAME_QUERY_TEMPLATE %
                      "','".join(host_names.split(',')))
  test_name, test_keys = chartutils.GetTestNameKeys(request.GET.get('testkey'))
  data_dict = GetKeysByBuildLinechartData(test_name, test_keys, chrome_versions,
                                          ' '.join(query_list))
  return data_dict
