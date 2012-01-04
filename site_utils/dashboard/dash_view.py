# Copyright (c) 2012 The Chromium OS Authors. All rights reserved.
# Use of this source code is governed by a BSD-style license that can be
# found in the LICENSE file.

"""Class for efficient data retrieval for dash utilities.

To see live data for these data structures best, run test_dash_view.py and
review its output. Output is produced by ShowDataModel() and ShowKeyVals().
"""

import datetime
import itertools
import logging
import os
import re

import dash_util
import test_summary

settings = "autotest_lib.frontend.settings"
os.environ["DJANGO_SETTINGS_MODULE"] = settings

# For db access.
from autotest_lib.frontend.afe import readonly_connection

# String resources.
from dash_strings import AUTOTEST_USER
from dash_strings import JOB_RESULT_DIR
from dash_strings import KERNELTEST_TAG
from dash_strings import LAST_N_JOBS_LIMIT
from dash_strings import LOCAL_TMP_DIR
from dash_strings import UNKNOWN_TIME_STR

# This used in SQL job matching.
JOB_MATCH = ("[-.][[:digit:]]+\.[[:digit:]]+\.[[:digit:]]+-"
             "[ar][[:alnum:]]*-b")
GTEST_SUFFIXES = ["browsertests", "pagecycler", "pyauto", "pyauto_basic",
                  "pyauto_perf", "sync"]
SUFFIXES_TO_SHOW = ["bvt", "flaky", "hwqual", "regression",
                    KERNELTEST_TAG] + GTEST_SUFFIXES
SERVER_JOB = "SERVER_JOB"


class CrashDashView(object):
  """View used to show crash information in summary and details views.

  An important reason we separate this class from AutotestDashView is that
  individual test details in AutotestDashView are frequently aliased into
  multiple categories.  To dedup crash results we use this separate structure.
  """

  def __init__(self, dash_base_dir):
    """Initialize grouping containers used to retrieve crashes.

    Crashes are summarized per build for entire platforms, categories and
    test names.  Data structures need to support retrieval of both detailed
    crash strings and counts of crashes discovered.

    The _crashes data structure is indexed as follows:
    +netbooks (netbook_HP_INDIANA, netbook_DELL_L13, ...)
    |+boards (x86-generic-bin, arm-generic-rel, ...)
     |+build
      |+test_name
       |-categories
       |-crash strings

    Args:
      dash_base_dir: root of the cache directory for crash results.
    """
    job_cache_dir = os.path.join(dash_base_dir, LOCAL_TMP_DIR, JOB_RESULT_DIR)
    dash_util.MakeChmodDirs(job_cache_dir)
    self._test_summaries = test_summary.TestSummaryInfo(job_cache_dir)
    self._crashes = {}

  def _LookupCrashDict(self, netbook, board, build, test_name=None):
    """Retrieve a leaf level (test_name) or one-up (build) of the crash tree.

    Args:
      netbook: one of our netbooks with the netbook_ prefix:
               netbook_DELL_L13, netbook_ANDRETTI, ...
      board: one of our boards: x86-generic-full, x86-mario-full-chromeos, ...
      build: a full build string: 0.8.73.0-r3ed8d12f-b719.
      test_name: test_name of Autotest test.

    Returns:
      Leaf level tuple of the category list and a dictionary for crash
      string details indexed on result instance idx.  If no test_name is
      supplied then the dict will contain crash results for all tests
      executed in that build (and the category list will be None).
    """
    netbook_dict = self._crashes.setdefault(netbook, {})
    board_dict = netbook_dict.setdefault(board, {})
    build_dict = board_dict.setdefault(build, {})
    if test_name:
      return build_dict.setdefault(test_name, (set(), {}))
    return None, build_dict

  def AddToCrashTree(self, netbook, board, build, test_name, result_idx,
                     job_tag):
    """Update the crash strings container from the results summary file.

    This crash strings container is optimized to support the two views
    that consume it: the waterfall summary view (platform x build) and the
    details view (platform x build x test_name).

    Args:
      netbook: one of our netbooks with the netbook_ prefix:
               netbook_DELL_L13, netbook_ANDRETTI, ...
      board: one of our boards: x86-generic-full, x86-mario-full-chromeos, ...
      build: a full build string: 0.8.73.0-r3ed8d12f-b719.
      test_name: test_name of Autotest test.
      result_idx: unique identifier for a test result instance.
      job_tag: path base for finding test result file under CAutotest results.
    """
    crash_strings = self._LookupCrashDict(netbook, board, build, test_name)[1]
    if result_idx in crash_strings:
      # The same test result can be attempted for entry because we alias
      # some test results under multiple categories.
      return
    job_crashes = self._test_summaries.RetrieveTestSummary(job_tag, test_name)
    if job_crashes and job_crashes.get('crashes'):
      crash_strings[result_idx] = job_crashes['crashes']

  def AddCrashCategory(self, netbook, board, build, test_name, category):
    """Keep a list of the categories assigned to this test_name.

    Used to hyperlink from a crash summary to it's related details page.

    Args:
      netbook: one of our netbooks with the netbook_ prefix:
               netbook_DELL_L13, netbook_ANDRETTI, ...
      board: one of our boards: x86-generic-full, x86-mario-full-chromeos, ...
      build: a full build string: 0.8.73.0-r3ed8d12f-b719.
      test_name: test_name of Autotest test.
      category: test category (test prefix or job suffix usually)
    """
    categories = self._LookupCrashDict(netbook, board, build, test_name)[0]
    categories.add(category)

  def GetBuildCrashSummary(self, netbook, board, build, category=None):
    """Used to populate the waterfall summary page with a crash count.

    The cells on the waterfall summary page reflect all crashes found from
    all tests in all categories for a given platform/build combination.  The
    cells on a category summary (kernel) page reflect crashes found only in a
    specific category for a given platform/build combination.

    Args:
      netbook: one of our netbooks with the netbook_ prefix:
               netbook_DELL_L13, netbook_ANDRETTI, ...
      board: one of our boards: x86-generic-full, x86-mario-full-chromeos, ...
      build: a full build string: 0.8.73.0-r3ed8d12f-b719.
      category: test category (test prefix or job suffix usually), None for all.

    Returns:
      Tuple used in watefall summary views of: crash_details list, a count
      of crashes and the first category for a hyperlink. The result tuple is
      ([], 0, None) if no crashes were discovered.
    """
    crashes = []
    n = 0
    all_categories = set()
    build_crashes = self._LookupCrashDict(netbook, board, build)[1]
    if build_crashes:
      for test_name in sorted(build_crashes):
        categories, crash_dict = build_crashes[test_name]
        if (not category) or (category and category in categories):
          new_crashes = sorted(list(itertools.chain(*crash_dict.values())))
          if new_crashes:
            crashes.append((test_name, new_crashes))
            n += len(new_crashes)
            all_categories |= categories
    if not crashes:
      return crashes, n, None
    return crashes, n, sorted(all_categories)[0]

  def GetBuildTestCrashSummary(self, netbook, board, build, test_name):
    """Used to populate the test details pages with crash counts per test.

    The cells on each category details page reflect crashes found only in a
    specific test for a given platform/build combination.

    Args:
      netbook: one of our netbooks with the netbook_ prefix:
               netbook_DELL_L13, netbook_ANDRETTI, ...
      board: one of our boards: x86-generic-full, x86-mario-full-chromeos, ...
      build: a full build string: 0.8.73.0-r3ed8d12f-b719.
      test_name: name of a specific test.

    Returns:
      Tuple used in details views: list of crash details and a count of crashes.
    """
    test_crashes = self._LookupCrashDict(netbook, board, build, test_name)[1]
    if not test_crashes:
      return [], 0
    new_crashes = sorted(list(itertools.chain(*test_crashes.values())))
    return new_crashes, len(new_crashes)

  def GetTestSummaries(self):
    """Test Summaries are used to probe the crash cache for crashes in a job.

    Used by the test result summary emailer to include crashes and a link to
    each job with a crash for research.

    Returns:
      The TestSummaryInfo object that is shared.
    """
    return self._test_summaries


class AutotestDashView(object):
  """View used by table_gen, plot_gen and dash_email."""

  class __impl:
    """Nested class implements code wrapped by singleton."""

    def __init__(self):
      """Setup common data structures for the models.

      Uses dashboard cache files for some (crash/timing) data.
      """
      self._dash_config = None
      self._cursor = readonly_connection.connection().cursor()
      self._common_where = (
          "WHERE job_name REGEXP %s"
          "  AND job_owner = %s"
          "  AND NOT ISNULL(test_finished_time)"
          "  AND NOT ISNULL(job_finished_time)"
          "  AND NOT test_name REGEXP 'CLIENT_JOB.*'"
          "  AND NOT test_name REGEXP '^boot\..*'"
          "  AND NOT test_name IN ('Autotest.install', 'cleanup_test', "
          "                        'lmbench', 'logfile.monitor', 'repair', "
          "                        'sleeptest', 'tsc')")
      # Used in expression parsing - have slightly different captures.
      self._jobname_parse = re.compile(
          '([\w-]*)-(.*[.-][\d]+\.[\d]+\.[\d]+-[ar][\w]+-b[\d]+)_([\w_]*)')
      self._subjob_parse1 = re.compile(
          '.*(0\.[\d]+\.[\d]+\.[\d]+-[ar][\w]+-b[\d]+)')
      self._subjob_parse2 = re.compile(
          '.*(R[\d]+-[\d]+\.[\d]+\.[\d]+-[ar][\w]+-b[\d]+)')
      self._board_parse = re.compile(
          '(x86|tegra2)-(.+)-(r[\d]+)')
      self._fullbuild_parse1 = re.compile(
          '[\d]+\.([\d]+)\.[\d]+\.[\d]+-[ar][\w]+-b([\d]+)')
      self._fullbuild_parse2 = re.compile(
          'R([\d]+)-[\d]+\.[\d]+\.[\d]+-[ar][\w]+-b([\d]+)')
      self._shortbuild_parse1 = re.compile(
          '([\d]+\.[\d]+\.[\d]+\.[\d]+)-([ar][\w]+)-b([\d]+)')
      self._shortbuild_parse2 = re.compile(
          '(R[\d]+-[\d]+\.[\d]+\.[\d]+)-([ar][\w]+)-b([\d]+)')
      self._release_parse = re.compile('r[\d]')

      # Test creation info (author, path).
      # Populated by QueryAutotests().
      self._autotests = {}

      self.TEST_TREE_DOC = """
      The test_tree is a dictionary of:
      +netbooks (netbook_HP_INDIANA, netbook_DELL_L13, ...)
      |+boards (x86-generic-bin, arm-generic-rel, ...)
       |+categories (platform, desktopui, bvt, regression, ...)
        |+test_name (platform_BootPerfServer, ...)
         |+builds (0.8.67.0-re7c459dc-b1135)
          |+indices [test_idx]
      This is our lookup index into tests.
      Populate netbooks by QueryNetbooks() and the rest by QueryTests().
      """
      self._test_tree = {}

      self.UI_CATEGORIES_DOC = """
      Many categories will not show on the dash but are available
      for use by emailer so must remain in the data model.
      This will be a subset of upper levels of the test_tree.
      +netbooks (netbook_HP_INDIANA, netbook_DELL_L13, ...)
      |+boards (x86-generic-bin, arm-generic-rel, ...)
       |+categories (platform, desktopui, bvt, regression, ...)
      Populated by QueryTests().
      """
      self._ui_categories = {}

      # Short subset of job_id's.
      # Populated by QueryBuilds().
      self._job_ids = set()

      self.BUILDS_DOC = """
      A little tree to track the builds for each of the boards.
      +board
      |-dictionary mapping short to long for lookups
      Populated by QueryBuilds().
      """
      self._builds = {}

      self.BUILD_TREE_DOC = """
      Need a tree of builds to show which builds were actually
      run for each netbook, board.
      +netbooks (netbook_HP_INDIANA, netbook_DELL_L13, ...)
      |+boards (x86-generic-bin, arm-generic-rel, ...)
       |+categories
        |+build
         |+aggregate build info
          |-latest job_id "job_id"
          |-earliest job started time "start"
          |-last job finished time "finish"
          |-number of 'GOOD' test names "ngood"
          |-number of total test names "ntotal"
      Used in netbook->board->category views.
      Populate netbooks by QueryNetbooks() and the rest by QueryTests().
      """
      self._build_tree = {}

      self.TESTS_DOC = """
      The test list is a dictionary of:
      +test_idx
      |+-test_name.
        -tag.
        -hostname.
        -status.
        -start (job_started_time)
        -finish (job_finished_time)
        -attr
      The actual test data. Used to fill popups and test status.
      Populated by QueryTests().
      """
      self._tests = {}

      self.CRASHES_DOC = """
      The crashes object is a container of crashes that may be
      filtered by build, category and test_name.
      """
      self._crashes = None

      self.PERF_KEYVALS_DOC = """
      For performance counters.
      +netbooks
      |+boards
      |+test_name
       |+key
        |+build
         |+(value_list, test_idx_list, iteration_list)
      Used in plotting.
      Populated by QueryKeyVals().
      """
      self._perf_keyvals = {}

      # Constant for date comparisons
      self._null_datetime = datetime.datetime(2010, 1, 1)
      self._null_timedelta = datetime.timedelta(0)

      # Performance optimization
      self._formatted_time_cache = {}
      self._last_updated = datetime.datetime.ctime(datetime.datetime.now())

    def CrashSetup(self, dash_base_dir):
      self._crashes = CrashDashView(dash_base_dir)

    def GetCrashes(self):
      """Accessor for crash data and functions."""
      return self._crashes

    def SetDashConfig(self, dash_config):
      """Some preprocessing of dash_config.

      Args:
        dash_config: dictionary of dash config entries.
      """
      self._dash_config = dash_config
      if 'customboardfilter' in dash_config:
        self._board_parse = re.compile(
            '(%s)-(.+)-(r[\d]+)' % dash_config['customboardfilter'])

    def GetAutotestInfo(self, name):
      """Return author and path of an autotest test.

      Args:
        name: Autotest test_name.

      Returns:
        2-Tuple of (author_name, test_path) used to locate test code.
      """
      name = name.split(".")[0]
      author = ""
      test_path = ""
      server_test_name = name + "Server"
      if name in self._autotests:
        author, test_path = self._autotests[name]
      elif server_test_name in self._autotests:
        author, test_path = self._autotests[server_test_name]
      if test_path:
        # convert server/tests/netpipe/control.srv --> server/tests/netpipe
        test_path = os.path.dirname(test_path)
      return author, test_path

    @property
    def netbooks(self):
      """Return a list of known netbooks - some may have not run tests.

      Returns:
        Unsorted List of all known netbooks (with netbook_ prefix). Some of
        these may have no tests run against them.
      """
      return self._test_tree.keys()

    def GetNetbooksWithBoardType(self, board):
      """Return list of netbooks with tests run under board.

      Args:
        board: one of our boards: x86-generic-full, x86-mario-full-chromeos, ...

      Returns:
        Sorted List of netbooks (with netbook_ prefix) that have completed
        tests associated with the given board.
      """
      netbooks = self._test_tree.keys()
      netbooks.sort()
      return [n for n in netbooks if board in self._test_tree[n]]

    def GetNetbooksWithBoardTypeCategory(self, board, category):
      """Return list of netbooks with tests under board and category.

      Args:
        board: one of our boards: x86-generic-full, x86-mario-full-chromeos, ...
        category: a test group: bvt, regression, desktopui, graphics, ...

      Returns:
        Sorted List of netbooks (with netbook_ prefix) that have completed
        tests of given category with the given board.
      """
      netbooks = self._build_tree.keys()
      netbooks.sort()
      return [n for n in netbooks if (
          board in self._build_tree[n] and
          category in self._build_tree[n][board])]

    def GetBoardTypes(self):
      """Return list of boards found.

      Returns:
        Unsorted List of all known boards: x86-generic-full,
        x86-mario-full-chromeos, ...
      """
      return self._builds.keys()

    def GetNetbookBoardTypes(self, netbook):
      """Return list of boards used in the given netbook.

      Args:
        netbook: one of our netbooks with the netbook_ prefix:
                 netbook_DELL_L13, netbook_ANDRETTI, ...

      Returns:
        Unsorted List of boards which have completed tests on the
        given netbook (with netbook_ prefix).
      """
      return self._build_tree[netbook].keys()

    def GetAllBuilds(self):
      """Return list of all known builds that we used.

      Returns:
        Unsorted Set of unique builds across all boards.
      """
      results = set()
      for build_dict in self._builds.itervalues():
        for b in build_dict.itervalues():
          results.add(b)
      return results

    def GetBoardtypeBuilds(
        self, board, limit=LAST_N_JOBS_LIMIT, asc=False):
      """Return list of builds with tests run in the given board.

      Args:
        board: one of our boards: x86-generic-full, x86-mario-full-chromeos, ...
        limit: common to truncate the build list for display.
        asc: if False, sort descending (tables) else ascending (plots).

      Returns:
        Sorted List of builds from with attempted jobs. These builds may
        NOT have associated test results if no tests completed on a
        netbook.
      """
      results = sorted(
          self._builds[board].values(),
          cmp=dash_util.BuildNumberCmp,
          reverse=asc)
      build_count = min(len(results), limit)
      if asc:
        return results[len(results)-build_count:]
      else:
        return results[:build_count]

    def GetBuilds(self, netbook, board, category):
      """Return list of builds with tests run in the given netbook.

      Args:
        netbook: one of our netbooks with the netbook_ prefix:
                 netbook_DELL_L13, netbook_ANDRETTI, ...
        board: one of our boards: x86-generic-full, x86-mario-full-chromeos, ...
        category: a test group: bvt, regression, desktopui, graphics, ...

      Returns:
        Sorted List of builds with jobs attempted on the given netbook,
        board combination with tests attempted in the given category.
        Again, tests may not have been completed thus there may be
        no corresponding test results.
      """
      results = []
      if not netbook in self._build_tree:
        return results
      if (board in self._build_tree[netbook] and
          category in self._build_tree[netbook][board]):
        for b in self._build_tree[netbook][board][category].iterkeys():
          if not b in self._builds[board]:
            logging.warn(
                "***DATA WARNING: %s not in build list for %s, %s, %s!",
                b, netbook, board, category)
          else:
            results.append(self._builds[board][b])
        results.sort(dash_util.BuildNumberCmp)
      return results

    def GetUICategories(self, netbook, board):
      """Return categories for DASH UI of tests run in netbook - board.

      Args:
        netbook: one of our netbooks with the netbook_ prefix:
                 netbook_DELL_L13, netbook_ANDRETTI, ...
        board: one of our boards: x86-generic-full, x86-mario-full-chromeos, ...

      Returns:
        Unsorted List of the UI categories (bvt, desktopui, ...) of tests
        with completed results run against the given netbook and board.
      """
      return list(self._ui_categories[netbook][board])

    def GetCategories(self, netbook, board):
      """Return categories of tests run in netbook - board.

      Args:
        netbook: one of our netbooks with the netbook_ prefix:
                 netbook_DELL_L13, netbook_ANDRETTI, ...
        board: one of our boards: x86-generic-full, x86-mario-full-chromeos, ...

      Returns:
        Unsorted List of the categories (bvt, desktopui, ...) of tests
        with completed results run against the given netbook and board.
      """
      if netbook in self._test_tree and board in self._test_tree[netbook]:
        return self._test_tree[netbook][board].keys()
      else:
        return []

    def GetTestNames(self, netbook, board, category):
      """Return unique test names run in netbook - board - category.

      Args:
        netbook: one of our netbooks with the netbook_ prefix:
                 netbook_DELL_L13, netbook_ANDRETTI, ...
        board: one of our boards: x86-generic-full, x86-mario-full-chromeos, ...
        category: a test group: bvt, regression, desktopui, graphics, ...

      Returns:
        Unsorted or empty List of test names for building a table
        listing all tests in the given category with completed results on
        the given netbook and board.
      """
      if category not in self._test_tree[netbook][board]:
        return []
      return self._test_tree[netbook][board][category].keys()

    def GetTestNamesInBuild(self, netbook, board, category, build):
      """Return the unique test names like GetTestNames() but for 1 build.

      Args:
        netbook: one of our netbooks with the netbook_ prefix:
                 netbook_DELL_L13, netbook_ANDRETTI, ...
        board: one of our boards: x86-generic-full, x86-mario-full-chromeos, ...
        category: a test group: bvt, regression, desktopui, graphics, ...
        build: a full build string: 0.8.73.0-r3ed8d12f-b719.

      Returns:
        Sorted or empty List of the test names in the given category and
        given build with completed test results against the given netbook
        and board.
      """
      results = []
      try:
        sequence = self.ParseShortFromBuild(build)
        for t, b in self._test_tree[netbook][board][category].iteritems():
          if sequence in b:
            results.append(t)
        results.sort()
      except KeyError:
        logging.warn("***KeyError: %s, %s, %s.", netbook, board, category)
      return results

    def GetCategorySummary(self, netbook, board, category, build):
      """Return ngood and ntotal for the given job.

      Args:
        netbook: one of our netbooks with the netbook_ prefix:
                 netbook_DELL_L13, netbook_ANDRETTI, ...
        board: one of our boards: x86-generic-full, x86-mario-full-chromeos, ...
        category: a test group: bvt, regression, desktopui, graphics, ...
        build: a full build string: 0.8.73.0-r3ed8d12f-b719.

      Returns:
        4-Tuple:
        -Boolean: True if the job was attempted
        -Boolean: True if all server jobs GOOD
        -Integer: number of tests completed GOOD
        -Integer: number of tests completed
      """
      ngood = 0
      ntotal = 0
      job_attempted = False
      job_good = False
      sequence = self.ParseShortFromBuild(build)
      if sequence in self._build_tree[netbook][board][category]:
        job = self._build_tree[netbook][board][category][sequence]
        ngood = job["ngood"]
        ntotal = job["ntotal"]
        job_good = job["server_good"]
        job_attempted = True
      return job_attempted, job_good, ngood, ntotal

    def TestDetailIterator(self, netbook, board, category, build):
      """Common iterator for looking through test details.

      Args:
        netbook: one of our netbooks with the netbook_ prefix:
                 netbook_DELL_L13, netbook_ANDRETTI, ...
        board: one of our boards: x86-generic-full, x86-mario-full-chromeos, ...
        category: a test group: bvt, regression, desktopui, graphics, ...
        build: a full build string: 0.8.73.0-r3ed8d12f-b719.

      Yields:
        Using Python generator (yield) mechanism return iterative test details.
      """
      tests = self.GetTestNamesInBuild(netbook, board, category, build)
      if not tests:
        return
      seq = self.ParseShortFromBuild(build)
      for test in tests:
        test_details = self.GetTestDetails(netbook, board, category, test, seq)
        if not test_details:
          continue
        for t in test_details:
          yield t

    def GetCategoryKernel(self, netbook, board, category, build):
      """Return string name of the kernel version like: 2.6.38.3+.

      Args:
        netbook: one of our netbooks with the netbook_ prefix:
                 netbook_DELL_L13, netbook_ANDRETTI, ...
        board: one of our boards: x86-generic-full, x86-mario-full-chromeos, ...
        category: a test group: bvt, regression, desktopui, graphics, ...
        build: a full build string: 0.8.73.0-r3ed8d12f-b719.

      Returns:
        String name of the kernel tested. If multiple kernels tested
        emit the one most used with a marker string.
      """
      kernel_votes = dash_util.SimpleCounter()
      for t in self.TestDetailIterator(netbook, board, category, build):
        kernel_votes.Push(t['attr'].get('sysinfo-uname', None))
      return kernel_votes.MaxKey()

    def GetCategoryFailedTests(self, netbook, board, category, build):
      """Return list of failed tests for easy popup display.

      Args:
        netbook: one of our netbooks with the netbook_ prefix:
                 netbook_DELL_L13, netbook_ANDRETTI, ...
        board: one of our boards: x86-generic-full, x86-mario-full-chromeos, ...
        category: a test group: bvt, regression, desktopui, graphics, ...
        build: a full build string: 0.8.73.0-r3ed8d12f-b719.

      Returns:
        List of unique test names of failed tests.
      """
      failed_tests = set()
      for t in self.TestDetailIterator(netbook, board, category, build):
        if t['status'] != 'GOOD':
          failed_tests.add(t['test_name'])
      return ', '.join(sorted(failed_tests))

    def GetJobTimes(self, netbook, board, category, seq):
      """Return job_start_time,  job_end_time and elapsed for the given job.

      Args:
        netbook: one of our netbooks with the netbook_ prefix:
                 netbook_DELL_L13, netbook_ANDRETTI, ...
        board: one of our boards: x86-generic-full, x86-mario-full-chromeos, ...
        category: a test group: bvt, regression, desktopui, graphics, ...
        seq: a short sequence from a build on this netbook and board.

      Returns:
        3-Tuple of Python datetime.datetime,datetime.datetime,datetime.timedelta
        for started_datetime, finished_datetime, elapsed_datetime.
        All are calculated across multiple jobs by looking at completed test
        results and choosing the earliest start time and the latest finish time.
      """
      job_started = self._null_datetime
      job_finished = self._null_datetime
      job_elapsed = self._null_timedelta
      if seq in self._build_tree[netbook][board][category]:
        job = self._build_tree[netbook][board][category][seq]
        job_started = job["start"]
        job_finished = job["finish"]
        job_elapsed = job_finished - job_started
      return job_started, job_finished, job_elapsed

    def GetJobTimesNone(self, netbook, board, category, seq):
      """Translate null_datetime from GetJobTimes() to None."""
      job_started, job_finished, job_elapsed = self.GetJobTimes(
          netbook, board, category, seq)
      if job_started == self._null_datetime:
        job_started = None
      if job_finished == self._null_datetime:
        job_finished = None
      if job_elapsed == self._null_datetime:
        job_elapsed = None
      return job_started, job_finished, job_elapsed

    def GetFormattedJobTimes(self, netbook, board, category, seq):
      """Return job_start_time, job_end_time and elapsed in datetime format.

      Args:
        netbook: one of our netbooks with the netbook_ prefix:
                 netbook_DELL_L13, netbook_ANDRETTI, ...
        board: one of our boards: x86-generic-full, x86-mario-full-chromeos, ...
        category: a test group: bvt, regression, desktopui, graphics, ...
        seq: a short sequence from a build on this netbook and board.

      Returns:
        3-Tuple of stringified started_datetime, finished_datetime, and
        elapsed_datetime. Returns a common string when invalid or no datetime
        was found.
      """
      time_key = (netbook, board, category, seq)
      if time_key in self._formatted_time_cache:
        return self._formatted_time_cache[time_key]
      job_started_str = UNKNOWN_TIME_STR
      job_finished_str = UNKNOWN_TIME_STR
      job_elapsed_str = UNKNOWN_TIME_STR
      job_started, job_finished, job_elapsed = self.GetJobTimes(*time_key)
      if job_started != self._null_datetime:
        job_started_str = datetime.datetime.ctime(job_started)
      if job_finished != self._null_datetime:
        job_finished_str = datetime.datetime.ctime(job_finished)
      if job_elapsed != self._null_timedelta:
        job_elapsed_str = str(job_elapsed)
      result = (job_started_str, job_finished_str, job_elapsed_str)
      self._formatted_time_cache[time_key] = result
      return result

    def GetFormattedLastUpdated(self):
      """Return a string used to date-time stamp our reports."""
      return self._last_updated

    def GetTestDetails(self, netbook, board, category, test_name, seq):
      """Return tests details for a given test_name x build cell.

      Args:
        netbook: one of our netbooks with the netbook_ prefix:
                 netbook_DELL_L13, netbook_ANDRETTI, ...
        board: one of our boards: x86-generic-full, x86-mario-full-chromeos, ...
        category: a test group: bvt, regression, desktopui, graphics, ...
        test_name: test_name of Autotest test.
        seq: a short sequence from a build on this netbook and board.

      Returns:
        Sorted or empty List of multiple test dictionaries for test instances
        in the given category that completed on the given netbook and board
        in the given build. The test dictionaries include common fields
        'test_name', 'tag', 'hostname', 'status' and an embedded dictionary
        of varying attributes under 'attr'.
      """
      test_details = []
      if seq in self._test_tree[netbook][board][category][test_name]:
        test_index_list = (list(
            self._test_tree[netbook][board][category][test_name][seq][0]))
        test_index_list.sort(reverse=True)
        for i in test_index_list:
          test_details.append(self._tests[i])
      return test_details

    def GetTestFromIdx(self, idx):
      """Returns all details about 1 specific instance of 1 test result.

      Args:
        idx: unique index of the test result.

      Returns:
        A Dictionary with attributes for a test result instance including tag.
      """
      return self._tests[str(idx)]

    def GetPlatformKeyValTests(self, netbook, board):
      """Return list of tests that have keyvals for a given netbook and board.

      Args:
        netbook: one of our netbooks with the netbook_ prefix:
                 netbook_DELL_L13, netbook_ANDRETTI, ...
        board: one of our boards: x86-generic-full, x86-mario-full-chromeos, ...

      Returns:
        None or a sorted list of the test names with keyvals.
      """
      if (not netbook in self._perf_keyvals or
          not board in self._perf_keyvals[netbook]):
        return []
      return sorted(self._perf_keyvals[netbook][board].keys())

    def GetTestKeys(self, netbook, board, test_name):
      """Return list of test keys with values for a given netbook and board.

      Args:
        netbook: one of our netbooks with the netbook_ prefix:
                 netbook_DELL_L13, netbook_ANDRETTI, ...
        board: one of our boards: x86-generic-full, x86-mario-full-chromeos, ...
        test_name: test_name of Autotest test.

      Returns:
        None or a sorted list of the test keys with keyvals.
      """
      if (not netbook in self._perf_keyvals or
          not board in self._perf_keyvals[netbook] or
          not test_name in self._perf_keyvals[netbook][board]):
        return None
      return sorted(self._perf_keyvals[netbook][board][test_name].keys())

    def GetTestKeyVals(self, netbook, board, test_name):
      """Return keyvals for one test over our queried jobs/builds.

      Args:
        netbook: one of our netbooks with the netbook_ prefix:
                 netbook_DELL_L13, netbook_ANDRETTI, ...
        board: one of our boards: x86-generic-full, x86-mario-full-chromeos, ...
        test_name: test_name of Autotest test.

      Returns:
        None or a dictionary of the performance key-values recorded during
        a completed test with the given netbook, board, test_name. The
        keyvals are from the overall set of jobs/builds that were discovered
        when querying the last n jobs/builds. The dictionary has keys of
        each performance key recorded and build dictionary. The build
        dictionary has keys of each build with the named performance key
        recorded and a value of the value list. The value list is a 2-Tuple
        of Lists. One is a list of the perf values and the other is a list
        of corresponding test_idx that may be used to look up job/test
        details from the point in a graphed plot.
      """
      if (not netbook in self._perf_keyvals or
          not board in self._perf_keyvals[netbook] or
          not test_name in self._perf_keyvals[netbook][board]):
        return None
      return self._perf_keyvals[netbook][board][test_name]

    def GetTestPerfVals(self, netbook, board, test_name, key):
      """Return values for one test/key over our queried jobs/builds.

      Args:
        netbook: one of our netbooks with the netbook_ prefix:
                 netbook_DELL_L13, netbook_ANDRETTI, ...
        board: one of our boards: x86-generic-full, x86-mario-full-chromeos, ...
        test_name: test_name of Autotest test.
        key: autotest perf key.

      Returns:
        None or a dictionary of the performance values recorded during
        a completed test with the given netbook, board, test_name, key. The
        vals are from the overall set of jobs/builds that were discovered
        when querying the last n jobs/builds.  The dictionary has keys of
        each build with the named performance key recorded and a value of
        the value list. The value list is a 2-Tuple of Lists. One is a
        list of the perf values and the other is a list of corresponding
        test_idx that may be used to look up job/test details from the
        point in a graphed plot.
      """
      keyvals = self.GetTestKeyVals(netbook, board, test_name)
      if keyvals and key in keyvals:
        return keyvals[key]
      return None

    def ParseBoard(self, board):
      """Return simple board without release identifier: e.g. x86-mario.

      Examples:
        stumpy-r16
        tegra2-kaen-r16
        tegra2-seaboard
        tegra2-seaboard-rc
        x86-alex-r16
        x86-generic-full
        x86-mario-r15

      Args:
        board: one of our boards: x86-generic-full, x86-mario-full-chromeos, ...

      Returns:
        (simple_board, release_if_found)
      """
      m = re.match(self._board_parse, board)
      if m and m.lastindex == 3:
        parsed_board = '%s-%s' % (m.group(1), m.group(2))
        release = m.group(3)
      else:
        split_board = board.split('-')
        found = False
        parsed_board = []
        for i in xrange(len(split_board)):
          if re.match(self._release_parse, split_board[i]):
            found = True
            break
          parsed_board.append(split_board[i])
        parsed_board = '-'.join(parsed_board)
        if found:
          release = split_board[i]
        else:
          release = None
      return parsed_board, release

    def ParseTestName(self, test_name):
      """Return category of test_name or a general category.

      A test_name defines a category if it has a prefix.

      Args:
        test_name: test_name from autotest db.

      Returns:
        Single token test category.
      """
      if test_name.find(".") > 0:
        test_name = test_name.split(".")[0]
      if test_name.find("_") > 0:
        category = test_name.split("_")[0]
      else:
        category = "autotest"

      return category

    def ParseJobName(self, job_name):
      """Return board - build# and job_suffix from the job_name.

      Args:
        job_name: complex string created by test_scheduler from a build image.

      Returns:
        Tuple of the board, a long build# and a possible job suffix (group).
      """
      m = re.match(self._jobname_parse, job_name)
      if not m or not len(m.groups()) == 3:
        logging.warn("***Invalid job_name: %s (%s).", job_name, len(m.groups()))
        return None, None, None
      board = m.group(1)
      # Subjob handles multi-build au test job names.
      n = re.match(self._subjob_parse1, m.group(2))
      if not n or not len(n.groups()) == 1:
        n = re.match(self._subjob_parse2, m.group(2))
      if not n or not len(n.groups()) == 1:
        full_build = None
      else:
        full_build = n.group(1)
      suffix = m.group(3)
      return board, full_build, suffix

    def ParseShortFromBuild(self, build):
      """Return the short build sequence number from the full build.

      A full build string: 0.8.73.0-r3ed8d12f-b719 includes a version
      (the 8) and a sequence (719) that are very useful. We aggregate
      the two to form a 'short' but unambiguous build#.

      Args:
        build: long/full build string.

      Returns:
        Short build sequence.
      """
      if not build:
        return None
      m = re.search(self._fullbuild_parse1, build)
      if not m or not len(m.groups()) == 2:
        m = re.search(self._fullbuild_parse2, build)
        if not m or not len(m.groups()) == 2:
          return None
      return str(int(m.group(1))*10000 + int(m.group(2)))

    def ParseSimpleBuild(self, build):
      """Strip out the 0.x.y.z portion of the build.

      A full build string: 0.8.73.0-r3ed8d12f-b719 includes a useful
      short build (0.8.73.0) and a sequence (719).  These are used in
      summaries.

      Args:
        build: long/full build string.

      Returns:
        The simple numeric build number.
      """
      m = re.match(self._shortbuild_parse1, build)
      if not m or not len(m.groups()) == 3:
        m = re.match(self._shortbuild_parse2, build)
      if not m or not len(m.groups()) == 3:
        parsed_build = build
      else:
        parsed_build = m.group(1)
      return parsed_build, self.ParseShortFromBuild(build)

    def LoadFromDB(self, job_limit=None):
      """Initial queries from the db for test tables.

      Args:
        job_limit: Limit query to last n jobs.
      """
      diag = dash_util.DebugTiming()
      if not self._autotests:
        self.QueryAutotests()
      if not self._test_tree:
        self.QueryNetbooks()
      if not self._builds:
        self.QueryBuilds(job_limit)
      if not self._tests:
        self.QueryTests()
      del diag

    def LoadPerfFromDB(self, job_limit=None):
      """Initial queries from db for perf checking.

      Args:
        job_limit: Limit query to last n jobs.
      """
      diag = dash_util.DebugTiming()
      self.LoadFromDB(job_limit)
      if not self._perf_keyvals:
        self.QueryKeyVals()
      del diag

    def QueryAutotests(self):
      """Get test attributes like author and path."""
      query = [
          "SELECT name, path, author",
          "FROM afe_autotests",
          "ORDER BY name"]
      self._cursor.execute(" ".join(query))
      for (name, path, author) in self._cursor.fetchall():
        self._autotests[name] = [author, path]

    def QueryNetbooks(self):
      """Get the netbooks know the to database."""
      query = [
          "SELECT name",
          "FROM afe_labels",
          "WHERE platform AND NOT invalid",
          "  AND name REGEXP '(netbook|desktop)_.*'",
          "UNION",
          "SELECT distinct machine_group as name",
          "FROM tko_machines",
          "WHERE machine_group REGEXP '(netbook|desktop)_.*'",
          "ORDER BY name"]
      self._cursor.execute(" ".join(query))
      for (netbook,) in self._cursor.fetchall():
        self._test_tree[netbook] = {}
        self._ui_categories[netbook] = {}
        self._build_tree[netbook] = {}

    def QueryBuilds(self, job_limit=None):
      """Get the boards and builds (jobs) to use.

      Args:
        job_limit: Limit query to last n jobs.
      """
      query = [
          "SELECT j.id, j.name, complete",
          "FROM afe_jobs AS j",
          "INNER JOIN afe_host_queue_entries AS q ON j.id = q.job_id",
          "WHERE name REGEXP %s AND owner = %s",
          "ORDER BY created_on DESC",
          "LIMIT %s"]
      if not job_limit:
        job_limit = LAST_N_JOBS_LIMIT
      params = [".*%s.*" % JOB_MATCH, AUTOTEST_USER, job_limit]
      self._cursor.execute(" ".join(query), params)

      incomplete_jobnames = set()
      jobname_to_jobid = {}

      for job_id, name, complete in self._cursor.fetchall():
        board, full_build, suffix = self.ParseJobName(name)
        if not board or not full_build or not suffix:
          logging.debug("Ignoring invalid: %s (%s, %s, %s).", name, board,
                        full_build, suffix)
          continue
        if suffix.startswith('kernel_'):
          suffix = KERNELTEST_TAG
        if (self._dash_config and
            'blacklistboards' in self._dash_config and
            board in self._dash_config['blacklistboards']):
          continue
        str_job_id = str(job_id)
        self._job_ids.add(str_job_id)
        sequence = self.ParseShortFromBuild(full_build)
        build_list_dict = self._builds.setdefault(board, {})
        build_list_dict.setdefault(sequence, full_build)
        # Track job_id's to later prune incomplete jobs.
        # Use a name common to all the jobs.
        tracking_name = "%s-%s" % (board, full_build)
        suffixes = jobname_to_jobid.setdefault(tracking_name, {})
        ids = suffixes.setdefault(suffix, [])
        ids.append(str_job_id)
        if not complete:
          incomplete_jobnames.add(name)

      # Now go prune out incomplete jobs.
      for name in incomplete_jobnames:
        logging.debug("Ignoring incomplete: %s.", name)
        board, full_build, suffix = self.ParseJobName(name)
        if suffix.startswith('kernel_'):
          suffix = KERNELTEST_TAG
        tracking_name = "%s-%s" % (board, full_build)
        if suffix in jobname_to_jobid[tracking_name]:
          for str_job_id in jobname_to_jobid[tracking_name][suffix]:
            if str_job_id in self._job_ids:
              self._job_ids.remove(str_job_id)
          del jobname_to_jobid[tracking_name][suffix]
        if not jobname_to_jobid[tracking_name]:
          sequence = self.ParseShortFromBuild(full_build)
          if sequence in self._builds[board]:
            del self._builds[board][sequence]

    def QueryTests(self):
      """Get and stash the test data and attributes."""
      if not self._job_ids:
        return
      query = [
          "SELECT test_idx, test_name, job_name, job_tag, afe_job_id,",
          "       platform, hostname, status, job_started_time,"
          "       job_finished_time, reason",
          "FROM tko_test_view_2",
          self._common_where,
          "  AND afe_job_id IN (%s)" % ",".join(self._job_ids),
          "ORDER BY job_idx DESC"]
      job_match = ".*%s.*" % JOB_MATCH
      params = [job_match, AUTOTEST_USER]
      self._cursor.execute(" ".join(query), params)
      results = self._cursor.fetchall()
      for (idx, test_name, job_name, job_tag, job_id, netbook,
           hostname, status, start_time, finish_time, reason) in results:
        if not netbook in self.netbooks:
          continue
        board, full_build, job_suffix = self.ParseJobName(job_name)
        if not board or not full_build or not job_suffix:
          continue
        sequence = self.ParseShortFromBuild(full_build)
        category = self.ParseTestName(test_name)
        ui_categories = self._ui_categories[netbook].setdefault(board, set())
        if job_suffix.startswith('kernel_'):
          job_suffix = KERNELTEST_TAG
        if job_suffix in SUFFIXES_TO_SHOW:
          ui_categories.add(job_suffix)
        if job_suffix in GTEST_SUFFIXES:
          category = job_suffix
        category_dict = self._test_tree[netbook].setdefault(board, {})

        if not test_name == SERVER_JOB:
          attribute_dict = {}
          attribute_dict["test_name"] = test_name
          attribute_dict["hostname"] = hostname
          attribute_dict["tag"] = job_tag
          attribute_dict["status"] = status
          attribute_dict["attr"] = {}
          if not status == 'GOOD':
            attribute_dict["attr"]["reason"] = reason[:min(len(reason), 120)]
          self._tests[str(idx)] = attribute_dict
          ui_categories.add(category)
          categories_to_load = [category, job_suffix]
          # Add crash string summary details.
          self._crashes.AddToCrashTree(netbook, board, full_build, test_name,
                                       idx, job_tag)
        else:
          categories_to_load = [job_suffix]

        for c in categories_to_load:
          self._crashes.AddCrashCategory(
              netbook, board, full_build, test_name, c)
          # Add earliest job started time and latest job_finished_time.
          build_board_dict = self._build_tree[netbook].setdefault(
              board, {})
          build_category_dict = build_board_dict.setdefault(c, {})
          build_info = build_category_dict.setdefault(sequence, {
              "start": datetime.datetime.now(),
              "finish": datetime.datetime(2010, 1, 1),
              "ngood": 0,
              "ntotal": 0,
              "server_good": True})

          if start_time < build_info["start"]:
            build_info["start"] = start_time
          if finish_time > build_info["finish"]:
            build_info["finish"] = finish_time

          if test_name == SERVER_JOB:
            if not status == "GOOD":
              build_info["server_good"] = False
            continue

          test_dict = category_dict.setdefault(c, {})
          build_dict = test_dict.setdefault(test_name, {})
          test_index_list = build_dict.setdefault(sequence, [set(), None])

          test_index_list[0].add(str(idx))
          if not test_index_list[1]:
            test_index_list[1] = status
            build_info["ntotal"] += 1
            if status == "GOOD":
              build_info["ngood"] += 1
          elif not status == "GOOD" and test_index_list[1] == "GOOD":
            build_info["ngood"] -= 1
            test_index_list[1] = status

      query = [
          "SELECT test_idx, attribute, value",
          "FROM tko_test_attributes",
          "WHERE test_idx in ('",
          "','".join(self._tests.keys()),
          "')",
          "ORDER BY test_idx, attribute"]
      self._cursor.execute(" ".join(query))
      for i, a, v in self._cursor.fetchall():
        self._tests[str(i)]["attr"][a] = v

    def QueryKeyVals(self):
      """Get the performance keyvals."""
      if not self._job_ids:
        return
      query = [
          "SELECT platform, job_name, hostname, test_idx, test_name, ",
          "       iteration_key, iteration, iteration_value",
          "FROM tko_perf_view_2 as p",
          "INNER JOIN tko_jobs as j USING (job_idx)",
          self._common_where,
          "  AND afe_job_id IN (%s)" % ",".join(self._job_ids),
          "AND NOT ISNULL(iteration_value)",
          "ORDER BY platform, job_name, test_name, iteration_key, ",
          "test_idx, iteration"]
      job_match = ".*%s.*" % JOB_MATCH
      params = [job_match, AUTOTEST_USER]
      self._cursor.execute(" ".join(query), params)
      results = self._cursor.fetchall()
      for (netbook, job_name, hostname, test_idx, test_name,
           iteration_key, iteration, iteration_value) in results:
        if iteration_value < 0:
          continue
        board, full_build, _ = self.ParseJobName(job_name)
        if not board or not full_build:
          continue
        sequence = self.ParseShortFromBuild(full_build)
        board_dict = self._perf_keyvals.setdefault(netbook, {})
        test_dict = board_dict.setdefault(board, {})
        key_dict = test_dict.setdefault(test_name, {})
        build_dict = key_dict.setdefault(iteration_key, {})
        value_list = build_dict.setdefault(sequence, ([], [], [], []))
        value_list[0].append(iteration_value)
        # Save test_idx to retrieve job details from data point.
        value_list[1].append(test_idx)
        # Save iteration for plotting.
        value_list[2].append(iteration)
        # Save hostname for plotting.
        value_list[3].append(hostname)

    def ShowDataModel(self):
      """Dump the data model for inspection."""
      dash_util.ShowStructure("AUTOTESTS", self._autotests)
      dash_util.ShowStructure("NETBOOKS", self.netbooks)
      dash_util.ShowStructure("BOARDS", self.GetBoardTypes())
      dash_util.ShowStructure("JOB IDS", self._job_ids)
      dash_util.ShowStructure(
          "BUILDS", self._builds, self.BUILDS_DOC)
      dash_util.ShowStructure(
          "BUILD TREE", self._build_tree, self.BUILD_TREE_DOC)
      dash_util.ShowStructure(
          "UI CATEGORIES", self._ui_categories, self.UI_CATEGORIES_DOC)
      dash_util.ShowStructure(
          "TEST TREE", self._test_tree, self.TEST_TREE_DOC)
      dash_util.ShowStructure(
          "TESTS WITH ATTRIBUTES", self._tests, self.TESTS_DOC)
      dash_util.ShowStructure(
          "CRASHES WITH TESTS AND CATEGORIES", self._crashes, self.CRASHES_DOC)

    def ShowKeyVals(self):
      """Dump the perf keyvals for inspection."""
      dash_util.ShowStructure(
          "PERF KEYVALS", self._perf_keyvals, self.PERF_KEYVALS_DOC)


  # Instance reference for singleton behavior.
  __instance = None
  __refs = 0

  def __init__(self):
    if AutotestDashView.__instance is None:
      AutotestDashView.__instance = AutotestDashView.__impl()

    self.__dict__["_AutotestDashView__instance"] = AutotestDashView.__instance
    AutotestDashView.__refs += 1

  def __del__(self):
    AutotestDashView.__refs -= 1
    if not AutotestDashView.__instance is None and AutotestDashView.__refs == 0:
      del AutotestDashView.__instance
      AutotestDashView.__instance = None

  def __getattr__(self, attr):
    return getattr(AutotestDashView.__instance, attr)

  def __setattr__(self, attr, value):
    return setattr(AutotestDashView.__instance, attr, value)


class SummaryRanges(object):
  """Each summary page needs list of each: boards, netbooks, builds."""

  def __init__(self, dash_view, category, summary_limit):
    self._summary_ranges = {}
    self._summary_kernels = {}
    boards = dash_view.GetBoardTypes()  # Some may not have tests.
    for board in boards:
      netbooks = dash_view.GetNetbooksWithBoardTypeCategory(
          board, category)
      netbooks.sort()

      # If all jobs were filtered by the summary, do not show that netbook
      # in the summary (it will show in the details view).
      build_numbers = dash_view.GetBoardtypeBuilds(board, summary_limit)
      build_number_set = set(build_numbers)
      netbooks_copy = netbooks[:]
      for netbook in netbooks_copy:
        netbook_set = set(dash_view.GetBuilds(
            netbook, board, category))
        if (build_number_set - netbook_set) == build_number_set:
          netbooks.remove(netbook)

      if netbooks:
        self._summary_ranges[board] = (netbooks, build_numbers)
        # Populate kernels
        self._summary_kernels[board] = {}
        for n in netbooks:
          self._summary_kernels[board][n] = {}
          for b in build_numbers:
            self._summary_kernels[board][n][b] = dash_view.GetCategoryKernel(
                n, board, category, b)

  def GetBoards(self):
    boards = self._summary_ranges.keys()
    boards.sort()
    return boards

  def GetNetbooks(self, board):
    return self._summary_ranges[board][0]

  def GetBuildNumbers(self, board):
    return self._summary_ranges[board][1]

  def GetKernel(self, board, netbook, build):
    try:
      return self._summary_kernels[board][netbook][build]
    except KeyError:
      return None
