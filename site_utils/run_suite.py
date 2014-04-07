#!/usr/bin/python
#
# Copyright (c) 2012 The Chromium OS Authors. All rights reserved.
# Use of this source code is governed by a BSD-style license that can be
# found in the LICENSE file.

"""Tool for running suites of tests and waiting for completion.

The desired test suite will be scheduled with autotest, and then
this tool will block until the job is complete, printing a summary
at the end.  Error conditions result in exceptions.

This is intended for use only with Chrome OS test suits that leverage the
dynamic suite infrastructure in server/cros/dynamic_suite.py.
"""

import datetime as datetime_base
import getpass, logging, optparse, os, re, sys, time
from datetime import datetime

import common

from autotest_lib.client.common_lib import global_config, enum
from autotest_lib.client.common_lib import priorities
from autotest_lib.frontend.afe.json_rpc import proxy
from autotest_lib.server import utils
from autotest_lib.server.cros.dynamic_suite import constants
from autotest_lib.server.cros.dynamic_suite import frontend_wrappers
from autotest_lib.server.cros.dynamic_suite import job_status
from autotest_lib.server.cros.dynamic_suite import reporting_utils
from autotest_lib.server.cros.dynamic_suite import tools
from autotest_lib.site_utils.graphite import stats
from autotest_lib.site_utils import diagnosis_utils

CONFIG = global_config.global_config

# Return code that will be sent back to autotest_rpc_server.py
RETURN_CODES = enum.Enum('OK', 'ERROR', 'WARNING')


def setup_logging(logfile=None):
    """Setup basic logging with all logging info stripped.

    Calls to logging will only show the message. No severity is logged.

    @param logfile: If specified dump output to a file as well.
    """
    # Remove all existing handlers. client/common_lib/logging_config adds
    # a StreamHandler to logger when modules are imported, e.g.,
    # autotest_lib.client.bin.utils. A new StreamHandler will be added here to
    # log only messages, not severity.
    logging.getLogger().handlers = []

    screen_handler = logging.StreamHandler()
    screen_handler.setFormatter(logging.Formatter('%(message)s'))
    logging.getLogger().addHandler(screen_handler)
    logging.getLogger().setLevel(logging.INFO)
    if logfile:
        file_handler = logging.FileHandler(logfile)
        file_handler.setLevel(logging.DEBUG)
        logging.getLogger().addHandler(file_handler)


def parse_options():
    #pylint: disable-msg=C0111
    usage = "usage: %prog [options]"
    parser = optparse.OptionParser(usage=usage)
    parser.add_option("-b", "--board", dest="board")
    parser.add_option("-i", "--build", dest="build")
    #  This should just be a boolean flag, but the autotest "proxy" code
    #  can't handle flags that don't take arguments.
    parser.add_option("-n", "--no_wait", dest="no_wait", default="False",
                      help='Must pass "True" or "False" if used.')
    # If you really want no pool, --pool="" will do it. USE WITH CARE.
    parser.add_option("-p", "--pool", dest="pool", default="suites")
    parser.add_option("-s", "--suite_name", dest="name")
    parser.add_option("-a", "--afe_timeout_mins", dest="afe_timeout_mins",
                      default=30)
    parser.add_option("-t", "--timeout_mins", dest="timeout_mins",
                      default=1440)
    parser.add_option("-d", "--delay_sec", dest="delay_sec", default=10)
    parser.add_option("-m", "--mock_job_id", dest="mock_job_id",
                      help="Skips running suite; creates report for given ID.")
    parser.add_option("-u", "--num", dest="num", type="int", default=None,
                      help="Run on at most NUM machines.")
    #  Same boolean flag issue applies here.
    parser.add_option("-f", "--file_bugs", dest="file_bugs", default='False',
                      help='File bugs on test failures. Must pass "True" or '
                           '"False" if used.')
    parser.add_option("-l", "--bypass_labstatus", dest="bypass_labstatus",
                      action="store_true", help='Bypass lab status check.')
    # We allow either a number or a string for the priority.  This way, if you
    # know what you're doing, one can specify a custom priority level between
    # other levels.
    parser.add_option("-r", "--priority", dest="priority",
                      default=priorities.Priority.DEFAULT,
                      action="store", help="Priority of suite")
    parser.add_option("--suite_args", dest="suite_args",
                      default=None, action="store",
                      help="Argument string for suite control file.")

    options, args = parser.parse_args()
    return parser, options, args


def verify_options_and_args(parser, options, args):
    """Verify the validity of options and args.

    @param parser: An OptionParser instance.
    @param options: The parsed options to verify.
    @param args: The parsed args to verify.

    @returns: True if verification passes, False otherwise.

    """
    if not options.mock_job_id:
        if args:
            print 'Unknown arguments: ' + str(args)
            return False
        if not options.build:
            print 'Need to specify which build to use'
            return False
        if not options.board:
            print 'Need to specify board'
            return False
        if not options.name:
            print 'Need to specify suite name'
            return False
    if options.num is not None and options.num < 1:
        print 'Number of machines must be more than 0, if specified.'
        return False
    if options.no_wait != 'True' and options.no_wait != 'False':
        print 'Please specify "True" or "False" for --no_wait.'
        return False
    if options.file_bugs != 'True' and options.file_bugs != 'False':
        print 'Please specify "True" or "False" for --file_bugs.'
        return False
    return True


def get_pretty_status(status):
    """
    Converts a status string into a pretty-for-printing string.

    @param status: Status to convert.

    @return: Returns pretty string.
             GOOD    -> [ PASSED ]
             TEST_NA -> [ INFO ]
             other   -> [ FAILED ]
    """
    if status == 'GOOD':
        return '[ PASSED ]'
    elif status == 'TEST_NA':
        return '[  INFO  ]'
    return '[ FAILED ]'


def is_fail_status(status):
    """
    Check if the given status corresponds to a failure.

    @param status: The status to check. (string)

    @return: True if status is FAIL or ERROR. False otherwise.
    """
    # All the statuses tests can have when they fail.
    if status in ['FAIL', 'ERROR', 'ABORT']:
        return True
    return False


class LogLink(object):
    """Information needed to record a link in the logs.

    Depending on context and the information provided at
    construction time, the link may point to either to log files for
    a job, or to a bug filed for a failure in the job.

    @var anchor  The link text.
    @var url     The link url.
    @var bug_id  Id of a bug to link to, or None.
    """

    _BUG_URL_PREFIX = CONFIG.get_config_value('BUG_REPORTING',
                                              'tracker_url')
    _URL_PATTERN = CONFIG.get_config_value('CROS',
                                           'log_url_pattern', type=str)


    def __init__(self, anchor, server, job_string, bug_info=None, reason=None):
        """Initialize the LogLink by generating the log URL.

        @param anchor      The link text.
        @param server      The hostname of the server this suite ran on.
        @param job_string  The job whose logs we'd like to link to.
        @param bug_info    Info about the bug, if one was filed.
        @param reason      A string representing the reason of failure if any.
        """
        self.anchor = anchor
        self.url = self._URL_PATTERN % (server, job_string)
        self.reason = reason
        if bug_info:
            self.bug_id, self.bug_count = bug_info
        else:
            self.bug_id = None
            self.bug_count = None


    def GenerateBuildbotLink(self):
        """Generate a link formatted to meet buildbot expectations.

        If there is a bug associated with this link, report that;
        otherwise report a link to the job logs.

        @return A link formatted for the buildbot log annotator.
        """
        if self.bug_id:
            url = '%s%s' % (self._BUG_URL_PREFIX, self.bug_id)
            if self.bug_count is None:
                anchor_text = '%s (Unknown number of reports)' % (
                        self.anchor.strip())
            elif self.bug_count == 1:
                anchor_text = '%s (new)' % self.anchor.strip()
            else:
                anchor_text = '%s (%s reports)' % (
                        self.anchor.strip(), self.bug_count)
        else:
            url = self.url
            anchor_text = self.anchor.strip()

        if self.reason:
            anchor_text = '%s - %s' % (anchor_text, self.reason)

        return '@@@STEP_LINK@%s@%s@@@'% (anchor_text, url)


    def GenerateTextLink(self):
        """Generate a link to the job's logs, for consumption by a human.

        @return A link formatted for human readability.
        """
        return '%s%s' % (self.anchor, self.url)


class Timings(object):
    """Timings for important events during a suite.

    All timestamps are datetime.datetime objects.

    @var suite_job_id: the afe job id of the suite job for which
                       we are recording the timing for.
    @var download_start_time: the time the devserver starts staging
                              the build artifacts. Recorded in create_suite_job.
    @var payload_end_time: the time when the artifacts only necessary to start
                           installsing images onto DUT's are staged.
                           Recorded in create_suite_job.
    @var artifact_end_time: the remaining artifacts are downloaded after we kick
                            off the reimaging job, at which point we record
                            artifact_end_time. Recorded in dynamic_suite.py.
    @var suite_start_time: the time the suite started.
    @var tests_start_time: the time the first test started running.
    @var tests_end_time: the time the last test finished running.
    """

    def __init__(self, suite_job_id):
        self.suite_job_id = suite_job_id
        # Timings related to staging artifacts on devserver.
        self.download_start_time = None
        self.payload_end_time = None
        self.artifact_end_time = None

        # The test_start_time, but taken off the view that corresponds to the
        # suite instead of an individual test.
        self.suite_start_time = None

        # Earliest and Latest tests in the set of TestViews passed to us.
        self.tests_start_time = None
        self.tests_end_time = None



    def _GetDatetime(self, timing_string, timing_string_format):
        """
        Formats the timing_string according to the timing_string_format.

        @param timing_string: A datetime timing string.
        @param timing_string_format: Format of the time in timing_string.
        @return: A datetime object for the given timing string.
        """
        try:
            return datetime.strptime(timing_string, timing_string_format)
        except TypeError:
            return None


    def RecordTiming(self, view):
        """Given a test report view, extract and record pertinent time info.

        get_detailed_test_views() returns a list of entries that provide
        info about the various parts of a suite run.  This method can take
        any one of these entries and look up timestamp info we might want
        and record it.

        If timestamps are unavailable, datetime.datetime.min/max will be used.

        @param view: a view dict, as returned by get_detailed_test_views().
        """
        start_candidate = datetime.min
        end_candidate = datetime.max
        if view['test_started_time']:
            start_candidate = datetime.strptime(view['test_started_time'],
                                                job_status.TIME_FMT)
        if view['test_finished_time']:
            end_candidate = datetime.strptime(view['test_finished_time'],
                                              job_status.TIME_FMT)

        if view['test_name'] == ResultCollector.SUITE_PREP:
            self.suite_start_time = start_candidate
        else:
            self._UpdateFirstTestStartTime(start_candidate)
            self._UpdateLastTestEndTime(end_candidate)
        if view['afe_job_id'] == self.suite_job_id and 'job_keyvals' in view:
            keyvals = view['job_keyvals']
            self.download_start_time = self._GetDatetime(
                keyvals.get(constants.DOWNLOAD_STARTED_TIME),
                job_status.TIME_FMT)

            self.payload_end_time = self._GetDatetime(
                keyvals.get(constants.PAYLOAD_FINISHED_TIME),
                job_status.TIME_FMT)

            self.artifact_end_time = self._GetDatetime(
                keyvals.get(constants.ARTIFACT_FINISHED_TIME),
                job_status.TIME_FMT)


    def _UpdateFirstTestStartTime(self, candidate):
        """Update self.tests_start_time, iff candidate is an earlier time.

        @param candidate: a datetime.datetime object.
        """
        if not self.tests_start_time or candidate < self.tests_start_time:
            self.tests_start_time = candidate


    def _UpdateLastTestEndTime(self, candidate):
        """Update self.tests_end_time, iff candidate is a later time.

        @param candidate: a datetime.datetime object.
        """
        if not self.tests_end_time or candidate > self.tests_end_time:
            self.tests_end_time = candidate


    def __str__(self):
        return ('\n'
                'Suite timings:\n'
                'Downloads started at %s\n'
                'Payload downloads ended at %s\n'
                'Suite started at %s\n'
                'Artifact downloads ended (at latest) at %s\n'
                'Testing started at %s\n'
                'Testing ended at %s\n' % (self.download_start_time,
                                           self.payload_end_time,
                                           self.suite_start_time,
                                           self.artifact_end_time,
                                           self.tests_start_time,
                                           self.tests_end_time))


    def _GetDataKeyForStatsd(self, suite, build, board):
        """
        Constructs the key used for logging statsd timing data.

        @param suite: scheduled suite that we want to record the results of.
        @param build: The build string. This string should have a consistent
            format eg: x86-mario-release/R26-3570.0.0. If the format of this
            string changes such that we can't determine build_type or branch
            we give up and use the parametes we're sure of instead (suite,
            board). eg:
                1. build = x86-alex-pgo-release/R26-3570.0.0
                   branch = 26
                   build_type = pgo-release
                2. build = lumpy-paladin/R28-3993.0.0-rc5
                   branch = 28
                   build_type = paladin
        @param board: The board that this suite ran on.
        @return: The key used to log timing information in statsd.
        """
        try:
            _board, build_type, branch = utils.ParseBuildName(build)[:3]
        except utils.ParseBuildNameException as e:
            logging.error(str(e))
            branch = 'Unknown'
            build_type = 'Unknown'
        else:
            embedded_str = re.search(r'x86-\w+-(.*)', _board)
            if embedded_str:
                build_type = embedded_str.group(1) + '-' + build_type

        data_key_dict = {
            'board': board,
            'branch': branch,
            'build_type': build_type,
            'suite': suite,
        }
        return ('run_suite.%(board)s.%(build_type)s.%(branch)s.%(suite)s'
                % data_key_dict)


    def SendResultsToStatsd(self, suite, build, board):
        """
        Sends data to statsd.

        1. Makes a data_key of the form: run_suite.$board.$branch.$suite
            eg: stats/gauges/<hostname>/run_suite/<board>/<branch>/<suite>/
        2. Computes timings for several start and end event pairs.
        3. Sends all timing values to statsd.

        @param suite: scheduled suite that we want to record the results of.
        @param build: the build that this suite ran on.
                      eg: 'lumpy-release/R26-3570.0.0'
        @param board: the board that this suite ran on.
        """
        if sys.version_info < (2, 7):
            logging.error('Sending run_suite perf data to statsd requires'
                          'python 2.7 or greater.')
            return

        data_key = self._GetDataKeyForStatsd(suite, build, board)

        # Since we don't want to try subtracting corrupted datetime values
        # we catch TypeErrors in _GetDatetime and insert None instead. This
        # means that even if, say, keyvals.get(constants.ARTIFACT_FINISHED_TIME)
        # returns a corrupt value the member artifact_end_time is set to None.
        if self.download_start_time:
            if self.payload_end_time:
                stats.Timer(data_key).send('payload_download_time',
                    (self.payload_end_time -
                     self.download_start_time).total_seconds())

            if self.artifact_end_time:
                stats.Timer(data_key).send('artifact_download_time',
                    (self.artifact_end_time -
                     self.download_start_time).total_seconds())

        if self.tests_end_time:
            if self.suite_start_time:
                stats.Timer(data_key).send('suite_run_time',
                    (self.tests_end_time -
                     self.suite_start_time).total_seconds())

            if self.tests_start_time:
                stats.Timer(data_key).send('tests_run_time',
                    (self.tests_end_time -
                     self.tests_start_time).total_seconds())


_DEFAULT_AUTOTEST_INSTANCE = CONFIG.get_config_value(
        'SERVER', 'hostname', type=str)


def instance_for_pool(pool_name):
    """
    Return the hostname of the server that should be used to service a suite
    for the specified pool.

    @param pool_name: The pool (without 'pool:' to schedule the suite against.
    @return: The correct host that should be used to service this suite run.
    """
    return CONFIG.get_config_value(
            'POOL_INSTANCE_SHARDING', pool_name,
            default=_DEFAULT_AUTOTEST_INSTANCE)


class ResultCollector(object):
    """Collect test results of a suite.

    Once a suite job has finished, use this class to collect test results.
    `run` is the core method that is to be called first. Then the caller
    could retrieve information like return code, return message, is_aborted,
    and timings by accessing the collector's public attributes. And output
    the test results and links by calling the 'output_*' methods.

    Here is a overview of what `run` method does.

    1) Collect the suite job's results from tko_test_view_2.
    For the suite job, we only pull test views without a 'subdir'.
    A NULL subdir indicates that the test was _not_ executed. This could be
    that no child job was scheduled for this test or the child job got
    aborted before starts running.
    (Note 'SERVER_JOB'/'CLIENT_JOB' are handled specially)

    2) Collect the child jobs' results from tko_test_view_2.
    For child jobs, we pull all the test views associated with them.
    (Note 'SERVER_JOB'/'CLIENT_JOB' are handled speically)

    3) Generate display names.
    Remove 'build/suite' prefix if any. And append 'exprimental' prefix
    for experimental tests.

    4) Compute timings of the suite run.
    5) Compute the return code based on test results.

    @var _instance_server: The hostname of the server that is used
                           to service the suite.
    @var _afe: The afe rpc client.
    @var _tko: The tko rpc client.
    @var _build: The build for which the suite is run,
                 e.g. 'lumpy-release/R35-5712.0.0'
    @var _suite_name: The suite name, e.g. 'bvt', 'dummy'.
    @var _suite_job_id: The job id of the suite for which we are going to
                        collect results.
    @var _suite_views: A list of relevant test views of the suite job.
    @var _child_views: A list of test views of the child jobs.
    @var _test_views: A list of all test views from _suite_views and
                      _child_views.
    @var _web_links: A list of web links pointing to the results of jobs.
    @var _buildbot_links: A list of buildbot links for non-passing tests.
    @var _display_names: A dictionary mapping test_idx to its formatted test
                         name that is to be shown in the output.
    @var return_code: The exit code that should be returned by run_suite.
    @var return_message: Any message that should be displayed to explain
                         the return code.
    @var is_aborted: Whether the suite was aborted or not.
                     True, False or None (aborting status is unknown yet)
    @var timings: A Timing object that records the suite's timings.

    """


    SUITE_PREP = 'Suite prep'


    def __init__(self, instance_server, afe, tko, build,
                 suite_name, suite_job_id):
        self._instance_server = instance_server
        self._afe = afe
        self._tko = tko
        self._build = build
        self._suite_name = suite_name
        self._suite_job_id = suite_job_id
        self._suite_views =[]
        self._child_views =[]
        self._test_views = []
        self._web_links = []
        self._buildbot_links = []
        self._display_names = {}
        self.return_code = None
        self.return_message=''
        self.is_aborted = None
        self.timings = None


    def is_test_experimental(self, view):
        """Check whether a test view is for an experimental test.

        @param view: A dictionary representing a tko test view.

        @return: True if it is for an experimental test, False otherwise.

        """
        return (view['job_keyvals'].get('experimental') == 'True' or
                tools.get_test_name(self._build, self._suite_name,
                        view['test_name']).startswith('experimental'))


    @staticmethod
    def _is_view_for_test(view):
        """Indicates whether the view of a given test is for an actual test.

        @param view: A dictionary representing a tko test view.
        @return True if the view is for an actual test.
                False if the view is for SERVER_JOB or CLIENT_JOB.

        """
        return not (view['test_name'].startswith('SERVER_JOB') or
                    view['test_name'].startswith('CLIENT_JOB'))


    def _fetch_relevant_test_views_of_suite(self):
        """Fetch relevant test views of the suite job.

        For the suite job, there will be a test view for SERVER_JOB, and views
        for results of its child jobs. For example, assume we've ceated
        a suite job (afe_job_id: 40) that runs dummy_Pass, dummy_Fail,
        dummy_Pass.bluetooth. Assume dummy_Pass was aborted before running while
        dummy_Path.bluetooth got TEST_NA as no duts have bluetooth.
        So the suite job's test views would look like
        _____________________________________________________________________
        test_idx| job_idx|test_name           |subdir      |afe_job_id|status
        10      | 1000   |SERVER_JOB          |----        |40        |GOOD
        11      | 1000   |dummy_Pass          |NULL        |40        |ABORT
        12      | 1000   |dummy_Fail.Fail     |41-onwer/...|40        |FAIL
        13      | 1000   |dummy_Fail.Error    |42-owner/...|40        |ERROR
        14      | 1000   |dummy_Pass.bluetooth|NULL        |40        |TEST_NA

        For a suite job, we only care about
        a) The test view for the suite job's SERVER_JOB
        b) The test views for real tests without a subdir. A NULL subdir
           indicates that a test didn't get executed.
        So, for the above example, we only keep test views whose test_idxs
        are 10, 11, 14.

        We also rename SERVER_JOB to 'Suite prep' in our local cache.

        @returns: A list of relevant test views of the suite job.

        """
        views = self._tko.run('get_detailed_test_views',
                             afe_job_id=self._suite_job_id)
        relevant_views = []
        for v in views:
            if v['test_name'] == 'SERVER_JOB':
                # Rename suite job's SERVER_JOB to 'Suite prep'.
                v['test_name'] = ResultCollector.SUITE_PREP
                relevant_views.append(v)
            elif (not v['test_name'].startswith('CLIENT_JOB') and
                  not v['subdir']):
                relevant_views.append(v)
        return relevant_views


    def _fetch_test_views_of_child_jobs(self):
        """Fetch test views of child jobs.

        For non-test test views like 'SERVER_JOB', 'CLIENT_JOB.0', we only
        keep it if it fails and the job has no other real test failures.
        And we also append the job name to the begining of its test name,
        so that it looks something like
        'lumpy-release/R35-5712.0.0/dummy/dummy_Fail_SERVER_JOB'. This is
        the naming convention that is used by dynamic suite for SERVER_JOB.
        We need to use the same name as dynamic suite does so that we can
        correctly retrieve any job keyval whose key includes test name as
        part of it.

        For test views of real test runs, we just keep them all.

        """
        child_job_ids = set(job.id for job in
                            self._afe.get_jobs(
                                parent_job_id=self._suite_job_id))
        child_views = []
        for job_id in child_job_ids:
            views = self._tko.run('get_detailed_test_views', afe_job_id=job_id)
            contains_test_failure = any(
                    ResultCollector._is_view_for_test(v) and
                    v['status'] != 'GOOD' for v in views)
            for v in views:
                if ResultCollector._is_view_for_test(v):
                    child_views.append(v)
                elif v['status'] != 'GOOD' and not contains_test_failure:
                    # This is SERVER_JOB or CLIENT_JOB. Only keep it
                    # if no other test failure. And append the job name
                    # as a prefix.
                    v['test_name'] = '%s_%s' % (v['job_name'], v['test_name'])
                    child_views.append(v)
        return child_views


    def _generate_display_names(self):
        """Generate display names.

        Formalize the test_name we got from the test view. Remove
        'build/suite' prefix if any. And append 'experimental' prefix
        for experimental tests if their names do not start with 'experimental'.

        If one runs a test in control file via the following code,
           job.runtest('my_Test', tag='tag')
        For most of the cases, test_name of the test view should
        look like 'my_Test.tag'.

        But there are three special cases.
        1) A test view is of a child job and for a SERVER_JOB or CLIENT_JOB.
           In this case, the test name has the job name as a prefix.
           If it is an experimental test, 'experimental' is as part of the name.
           For instance,
           'lumpy-release/R35-5712.0.0/perf_v2/
                   experimental_Telemetry Smoothness Measurement_SERVER_JOB'
           'lumpy-release/R35-5712.0.0/dummy/
                   experimental_dummy_Pass_SERVER_JOB'
           'lumpy-release/R35-5712.0.0/dummy/dummy_Fail_SERVER_JOB'

        2) A test view's status is of a suite job and its status is ABORT.
           In this case, the test name is the job name.
           If it is an experimental test, 'experimental' is part of the name.
           For instance,
           'lumpy-release/R35-5712.0.0/perf_v2/
                   experimental_Telemetry Smoothness Measurement'
           'lumpy-release/R35-5712.0.0/dummy/experimental_dummy_Pass'
           'lumpy-release/R35-5712.0.0/dummy/dummy_Fail'

        3) A test view's status is of a suite job and its status is TEST_NA.
           In this case, the test name is NAME field of the control file.
           If it is an experimental test, 'experimental' is part of the name.
           For instance, 'experimental_Telemetry Smoothness Measurement'
                         'experimental_dummy_Pass'
                         'dummy_Fail'

        """
        max_width = 0
        self._display_names = {}
        for v in self._test_views:
            experimental =  self.is_test_experimental(v)
            test_name = tools.get_test_name(
                    self._build, self._suite_name, v['test_name'])
            # If an experimental test was aborted, test_name
            # would include the 'experimental' prefix already.
            prefix = constants.EXPERIMENTAL_PREFIX if (
                    experimental and not
                    test_name.startswith(constants.EXPERIMENTAL_PREFIX)) else ''
            display_name = prefix + test_name
            width = len(display_name)
            if max_width < width:
                max_width = width
            self._display_names[v['test_idx']] = display_name
        self._max_testname_width = max_width + 3


    def _generate_web_and_buildbot_links(self):
        """Generate web links and buildbot links."""
        # TODO(fdeng): If a job was aborted before it reaches Running
        # state, we read the test view from the suite job
        # and thus this method generates a link pointing to the
        # suite job's page for the aborted job. Need a fix.
        self._web_links = []
        self._buildbot_links = []
        # Bug info are stored in the suite job's keyvals.
        suite_job_keyvals = self._suite_views[0]['job_keyvals']
        for v in self._test_views:
            bug_info = tools.get_test_failure_bug_info(
                    suite_job_keyvals, v['afe_job_id'], v['test_name'])
            job_id_owner = '%s-%s' % (v['afe_job_id'], getpass.getuser())
            link = LogLink(
                    anchor=self._display_names[v['test_idx']].ljust(
                            self._max_testname_width),
                    server=self._instance_server,
                    job_string=job_id_owner,
                    bug_info=bug_info)
            self._web_links.append(link)

            # Don't show links on the buildbot waterfall for tests with
            # GOOD status.
            if v['status'] != 'GOOD' and v['status'] != 'TEST_NA':
                link.reason = '%s: %s' % (v['status'], v['reason'])
                self._buildbot_links.append(link)


    def _record_timings(self):
        """Record suite timings."""
        self.timings = Timings(self._suite_job_id)
        for v in self._test_views:
            self.timings.RecordTiming(v)


    def _compute_return_code(self):
        """Compute the exit code based on test results."""
        code = RETURN_CODES.OK
        for v in self._test_views:
            # Any non experimental test that has a status other than WARN
            # or GOOD will result in the tree closing. Experimental tests
            # will not close the tree, even if they have been aborted.
            if not self.is_test_experimental(v):
                if v['status'] == 'WARN':
                    code = RETURN_CODES.WARNING
                elif is_fail_status(v['status']):
                    code = RETURN_CODES.ERROR
                    # Failed already, no need to worry further.
                    break
        self.return_code = code


    def output_results(self):
        """Output test results, timings and web links."""
        # Output test results
        for v in self._test_views:
            display_name = self._display_names[v['test_idx']].ljust(
                    self._max_testname_width)
            logging.info('%s%s', display_name,
                         get_pretty_status(v['status']))
            if v['status'] != 'GOOD':
                logging.info("%s  %s: %s", display_name, v['status'],
                             v['reason'])
        # Output suite timings
        logging.info(self.timings)
        # Output links to test logs
        logging.info('\nLinks to test logs:')
        for link in self._web_links:
            logging.info(link.GenerateTextLink())


    def output_buildbot_links(self):
        """Output buildbot links."""
        for link in self._buildbot_links:
            logging.info(link.GenerateBuildbotLink())


    def run(self):
        """Collect test results.

        This method goes through the following steps:
            Fetch relevent test views of the suite job.
            Fetch test views of child jobs
            Check whether the suite was aborted.
            Generate the test names to display in the output.
            Calculate suite timings.
            Compute return code based on the test result.

        """
        self._suite_views = self._fetch_relevant_test_views_of_suite()
        self._child_views = self._fetch_test_views_of_child_jobs()
        self._test_views = self._suite_views + self._child_views
        # For hostless job in Starting status, there is no test view associated.
        # This can happen when a suite job in Starting status is aborted. When
        # the scheduler hits some limit, e.g., max_hostless_jobs_per_drone,
        # max_jobs_started_per_cycle, a suite job can stays in Starting status.
        if not self._test_views:
            self.return_code = RETURN_CODES.ERROR
            self.return_message = 'No test view was found.'
            return
        self.is_aborted = any([view['job_keyvals'].get('aborted_by')
                               for view in self._suite_views])
        self._generate_display_names()
        self._generate_web_and_buildbot_links()
        self._record_timings()
        self._compute_return_code()


def main():
    """
    Entry point for run_suite script.
    """
    parser, options, args = parse_options()
    if not verify_options_and_args(parser, options, args):
        parser.print_help()
        return

    log_name = 'run_suite-default.log'
    if not options.mock_job_id:
        # convert build name from containing / to containing only _
        log_name = 'run_suite-%s.log' % options.build.replace('/', '_')
        log_dir = os.path.join(common.autotest_dir, 'logs')
        if os.path.exists(log_dir):
            log_name = os.path.join(log_dir, log_name)

    setup_logging(logfile=log_name)
    try:
        priority = int(options.priority)
    except ValueError:
        try:
            priority = priorities.Priority.get_value(options.priority)
        except AttributeError:
            print 'Unknown priority level %s.  Try one of %s.' % (
                  options.priority, ', '.join(priorities.Priority.names))

    try:
        if not options.bypass_labstatus:
            utils.check_lab_status(options.build)
    except utils.TestLabException as e:
        logging.warning('Error Message: %s', e)
        return RETURN_CODES.WARNING

    instance_server = instance_for_pool(options.pool)
    afe = frontend_wrappers.RetryingAFE(server=instance_server,
                                        timeout_min=options.afe_timeout_mins,
                                        delay_sec=options.delay_sec)
    logging.info('Autotest instance: %s', instance_server)

    wait = options.no_wait == 'False'
    file_bugs = options.file_bugs == 'True'
    logging.info('%s Submitted create_suite_job rpc',
                 diagnosis_utils.JobTimer.format_time(datetime.now()))
    if options.mock_job_id:
        job_id = int(options.mock_job_id)
    else:
        job_id = afe.run('create_suite_job', suite_name=options.name,
                         board=options.board, build=options.build,
                         check_hosts=wait, pool=options.pool, num=options.num,
                         file_bugs=file_bugs, priority=priority,
                         suite_args=options.suite_args,
                         wait_for_results=wait,
                         timeout_mins=options.timeout_mins)
    job_timer = diagnosis_utils.JobTimer(
            time.time(), float(options.timeout_mins))
    logging.info('%s Created suite job: %s',
                 job_timer.format_time(job_timer.job_created_time),
                 reporting_utils.link_job(
                        job_id, instance_server=instance_server))

    TKO = frontend_wrappers.RetryingTKO(server=instance_server,
                                        timeout_min=options.afe_timeout_mins,
                                        delay_sec=options.delay_sec)
    code = RETURN_CODES.OK
    rpc_helper = diagnosis_utils.RPCHelper(afe)
    if wait:
        while not afe.get_jobs(id=job_id, finished=True):
            # Note that this call logs output, preventing buildbot's
            # 9000 second silent timeout from kicking in. Let there be no
            # doubt, this is a hack. The timeout is from upstream buildbot and
            # this is the easiest work around.
            if job_timer.first_past_halftime():
                rpc_helper.diagnose_job(job_id)
                logging.info('The suite job has another %s till timeout \n',
                             job_timer.timeout_hours - job_timer.elapsed_time())
            time.sleep(10)

        # Start collecting test results.
        collector = ResultCollector(instance_server=instance_server,
                                    afe=afe, tko=TKO, build=options.build,
                                    suite_name=options.name,
                                    suite_job_id=job_id)
        collector.run()
        # Output test results, timings, web links.
        collector.output_results()
        # Get exit code that should be returned by run_suite.
        # And output return message.
        code = collector.return_code
        code_str = RETURN_CODES.get_string(collector.return_code)
        return_message = '\nWill return from run_suite with status:  %s'
        if collector.return_message:
            return_message = '%s (%s)' % (
                    return_message, collector.return_message)
        logging.info(return_message, code_str)
        # Send timings to statsd. Do not record stats if the suite was
        # aborted (either by a user or through the golo rpc).
        # Also do not record stats if is_aborted is None, indicating
        # aborting status is unknown yet.
        if collector.is_aborted == False and not options.mock_job_id:
            collector.timings.SendResultsToStatsd(options.name, options.build,
                                                  options.board)
        # There is a minor race condition here where we might have aborted for
        # some reason other than a timeout, and the job_timer thinks it's a
        # timeout because of the jitter in waiting for results. This shouldn't
        # harm us since all diagnose_pool does is log information about a pool.
        if job_timer.is_suite_timeout():
            logging.info('\nAttempting to diagnose pool: %s', options.pool)
            try:
                # Add some jitter to make up for any latency in
                # aborting the suite or checking for results.
                cutoff = (job_timer.timeout_hours +
                          datetime_base.timedelta(hours=0.3))
                rpc_helper.diagnose_pool(
                        options.board, options.pool, cutoff)
            except proxy.JSONRPCException as e:
                logging.warning('Unable to diagnose suite abort.')

        logging.info('\nOutput below this line is for buildbot consumption:')
        collector.output_buildbot_links()
    else:
        logging.info('Created suite job: %r', job_id)
        link = LogLink(options.name, instance_server,
                       '%s-%s' % (job_id, getpass.getuser()))
        logging.info(link.GenerateBuildbotLink())
        logging.info('--no_wait specified; Exiting.')
    return code


if __name__ == "__main__":
    sys.exit(main())
