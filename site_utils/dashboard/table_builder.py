# Copyright (c) 2012 The Chromium OS Authors. All rights reserved.
# Use of this source code is governed by a BSD-style license that can be
# found in the LICENSE file.

"""Class to wrap building detail table for board/netbook/testcategory."""

import os

import dash_util

from build_info import BuildInfo
from dash_view import AutotestDashView

# String resources.
from dash_strings import BVT_TAG

# Constants
DEFAULT_TEST_NAME_LENGTH = 18


class TableBuilder(object):
  """Class manages building header and body for details tables."""

  def __init__(self, base_dir, netbook, board_type, category):
    self._netbook = netbook
    self._board_type = board_type
    self._category = category
    self._build_info = BuildInfo()
    self._dash_view = AutotestDashView()
    self._test_list = self._dash_view.GetTestNames(
        netbook, board_type, category)
    self._test_list.sort()
    self._build_numbers = self._dash_view.GetBuilds(
        netbook, board_type, category)
    self._good_set, self._failed_list = self._SplitTestList()

  def  _SplitTestList(self):
    """Determine and list the tests that passed and failed."""
    good_set = set()
    failed_list = []  # Maintains order discovered.

    for build in self._build_numbers:
      for test_name in self._test_list:
        test_details = self._GetTestDetails(test_name, build)
        if test_details:
          for t in test_details:
            good_status = (t['status'] == 'GOOD')
            test_tuple = (test_name, t['experimental'])
            if test_tuple in failed_list:
              continue
            if good_status:
              good_set.add(test_tuple)
            else:
              failed_list.append(test_tuple)
              good_set.discard(test_tuple)
    return sorted(good_set), failed_list

  def _BuildTableHeader(self, test_list):
    """Generate header with test names for columns."""
    table_header = []
    for test_name, experimental in test_list:
      test_path = self._dash_view.GetAutotestInfo(test_name)[1]
      if len(test_name) > DEFAULT_TEST_NAME_LENGTH:
        test_alias = test_name[:DEFAULT_TEST_NAME_LENGTH] + '...'
      else:
        test_alias = test_name
      table_header.append((test_path, test_alias.replace('_', ' '),
                           test_name, experimental))
    return table_header

  def _GetBuildMetadata(self, build):
    """Retrieve info used to populate build header popups."""
    started, finished, elapsed = self._dash_view.GetFormattedJobTimes(
        self._netbook, self._board_type, self._category, build)
    fstarted, ffinished, felapsed, ffinished_short = (
        self._build_info.GetFormattedBuildTimes(self._board_type, build))
    return (fstarted, ffinished, felapsed,
            started, finished, elapsed,
            self._dash_view.GetFormattedLastUpdated())

  def _GetTestDetails(self, test_name, build):
    return self._dash_view.GetTestDetails(
        self._netbook, self._board_type, self._category, test_name, build)

  def _BuildTableBody(self, test_list):
    """Generate table body with test results in cells."""
    table_body = []

    for build in self._build_numbers:
      chrome_version = self._build_info.GetChromeVersion(self._board_type,
                                                         build)
      test_status_list = []
      for test_name, experimental in test_list:
        # Include either the good details or the details of the
        # first failure in the list (last chronological failure).
        cell_content = []
        test_details = self._GetTestDetails(test_name, build)
        if test_details:
          total_tests = len(test_details)
          passed_tests = 0
          failed_tests = 0
          for t in test_details:
            current_fail = False
            test_status = t['status']
            if test_status == 'GOOD':
              passed_tests += 1
              query = '%(tag)s' % t
            else:
              failed_tests += 1
              current_fail = True
              query = '%(tag)s/%(test_name)s' % t
            # Populate the detailed cell popups prudently.
            host_info = []
            chrome_version_attr = chrome_version
            if chrome_version and len(chrome_version) == 2:
              chrome_version_attr = '%s (%s)' % (chrome_version[0],
                                                 chrome_version[1])
            priority_attrs = [
                ('Chrome Version', 'chrome-version', chrome_version_attr),
                ('ChromeOS Version', 'CHROMEOS_RELEASE_DESCRIPTION', None),
                ('Platform', 'host-platform', None),
                ('Kernel Version', 'sysinfo-uname', None),
                ('Reason', 'reason', None)]
            for popup_header, attr_key, default in priority_attrs:
              attr_value = t['attr'].get(attr_key, default)
              if attr_value:
                host_info.append((popup_header, attr_value))
            test_status = test_status[0].upper()
            # Treat TEST_NA as WARNING.
            if test_status == 'T':
              test_status = 'W'
            if (not cell_content) or (current_fail and failed_tests == 1):
              cell_content = [test_name, t['hostname'], host_info, query,
                              test_status]
          if cell_content:
            test_summaries = [passed_tests, total_tests]
            test_summaries.extend(
                self._dash_view.GetCrashes().GetBuildTestCrashSummary(
                    self._netbook, self._board_type, build, test_name))
            cell_content.extend(test_summaries)
        test_status_list.append(cell_content)
      popup = self._GetBuildMetadata(build)
      table_body.append(('', build, popup, test_status_list, chrome_version))
    return table_body

  def BuildTables(self):
    """Generate table body with test results in cells."""
    good_table_header = self._BuildTableHeader(self._good_set)
    good_table_body = self._BuildTableBody(self._good_set)
    result = [{'label': 'Good Tests',
               'header': good_table_header,
               'body': good_table_body}]
    if self._failed_list:
      failed_table_header = self._BuildTableHeader(self._failed_list)
      failed_table_body = self._BuildTableBody(self._failed_list)
      result.insert(0, {'label': 'Failed Tests',
                        'header': failed_table_header,
                        'body': failed_table_body})
    return result

  def CountTestList(self):
    """Count the number of tests and failed ones."""
    if self._build_numbers:
      return len(self._good_set)+len(self._failed_list), len(self._failed_list)
    else:
      return 0, 0
