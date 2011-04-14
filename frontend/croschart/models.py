# Copyright (c) 2011 The Chromium OS Authors. All rights reserved.
# Use of this source code is governed by a BSD-style license that can be
# found in the LICENSE file.


import logging
import os
import re

from autotest_lib.frontend.afe import readonly_connection


BUILD_PATTERN = re.compile(
    '[\w]*\-[\w]*\-r[\w]*\-'
      '([\d]*\.[\d]*\.[\d]*\.[\d]*)-(r[\w]{8})-(b[\d]*)')


def AbbreviateBuild(build):
    m = re.match(BUILD_PATTERN, build)
    if not m:
      logging.warning('Skipping poorly formatted build: %s.', build)
      return build
    new_build = '%s-%s' % (m.group(1), m.group(3))
    return new_build


def AggregateBuilds(test_key, data_list):
  build_dict = {}
  build_order = []
  job_tags = []
  for build, tag, value in data_list:
    build = AbbreviateBuild(build)
    if not build in build_dict:
      build_order.append(build)
      job_tags.append(tag)
    build_dict.setdefault(build, []).append(value)
  gviz_build_data = []
  for build in build_order:
    value_list = build_dict[build]
    gviz_build_data.append({
        'build': build,
        test_key: round(sum(value_list, 0.0) / len(value_list), 2)})
  return gviz_build_data, job_tags


def GetChartData(boards, netbook, from_build, to_build,
                 test_name, test_key, interval):
  cursor = readonly_connection.connection().cursor()

  # Common query template that gets re-used.
  platform = 'netbook_%s' % netbook
  common_query = [
      "SELECT %s",
      "FROM tko_perf_view_2",
      "WHERE job_name REGEXP %s",
      "  AND platform = '%s'" % platform,
      "  AND test_name = '%s'" % test_name,
      "  AND iteration_key = '%s'" % test_key,
      "  AND job_owner = 'chromeos-test'",
      "  AND NOT ISNULL(iteration_value)",
      "  AND iteration_value >= 0.0",
      "  AND NOT ISNULL(test_started_time)",
      "  AND NOT ISNULL(test_finished_time)",
      "  AND NOT ISNULL(job_finished_time)"]
  common_job_name = "'(%s).*'"

  # Query notes:
  # 1. Getting the job_name to be able to aggregate different jobs that run
  #    the same test on the same build.
  # 2. Getting every data point to be able to discard outliers.
  # 3. Default order of date.
  # 4. Uses subqueries to find bracketing dates mapping version to job_names.
  if from_build:
    job_name = common_job_name % '|'.join(
        '%s-%s' % (b, from_build.replace('.', '\.')) for b in boards.split('&'))
    min_query = ' '.join(common_query) % (
        'IFNULL(MIN(test_started_time), DATE_SUB(NOW(), INTERVAL 1 DAY))',
        job_name)
  else:
    if not interval:
      interval = '2 WEEK'
    min_query = 'SELECT DATE_SUB(NOW(), INTERVAL %s)' % interval

  if to_build:
    job_name = common_job_name % '|'.join(
        '%s-%s' % (b, to_build.replace('.', '\.')) for b in boards.split('&'))
    max_query = ' '.join(common_query) % (
        'IFNULL(MAX(test_started_time), NOW())', job_name)
  else:
    max_query = 'SELECT NOW()'

  iteration_values = 'job_name, job_tag, iteration_value'
  job_name = common_job_name % '|'.join(boards.split('&'))
  query = [
      ' '.join(common_query) % (iteration_values, job_name),
      '  AND test_started_time > (%s)' % min_query,
      '  AND test_finished_time < (%s)' % max_query,
      'ORDER BY test_started_time']
  cursor.execute(' '.join(query))
  return AggregateBuilds(test_key, cursor.fetchall())
