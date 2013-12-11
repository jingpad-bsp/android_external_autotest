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

import getpass, hashlib, logging, optparse, os, re, sys, time
from datetime import datetime

import common

from autotest_lib.client.common_lib import global_config, enum
from autotest_lib.client.common_lib import priorities
from autotest_lib.server import utils
from autotest_lib.server.cros.dynamic_suite import constants
from autotest_lib.server.cros.dynamic_suite import frontend_wrappers
from autotest_lib.server.cros.dynamic_suite import job_status
from autotest_lib.server.cros.dynamic_suite import tools
from autotest_lib.site_utils.graphite import stats

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
    parser.add_option("-p", "--pool", dest="pool", default="")
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


def get_view_info(suite_job_id, view, build, suite):
    """
    Parse a view for the slave job name and job_id.

    @param suite_job_id: The job id of our master suite job.
    @param view: Test result view.
    @param build: build passed in via the -b option.
        eg: lumpy-release/R28-3947.0.0
    @param suite: suite passed in via the -s option.
        eg: dummy
    @return A tuple job_name, experimental, name of the slave test run
            described by view. eg:
            experimental_dummy_Pass fails: (1130-owner, True, dummy_Pass)
            experimental_dummy_Pass aborts: (1130-owner, True,
                                             experimental_dummy_Pass)
            dummy_Fail: (1130-owner, False, dummy_Fail.Error)
    """
    # By default, we are the main suite job since there is no
    # keyval entry for our job_name.
    job_name = '%s-%s' % (suite_job_id, getpass.getuser())
    experimental = False
    test_name = ''
    # raw test name is the test_name from tko status view. tko_job_keyvals may
    # have a record of the hash of this name mapping to job_id-owner, which can
    # be used to reference the test to its job url. The change is made to
    # support tests in different jobs within a suite that shares the same test
    # class, e.g., AU suite.
    raw_test_name = view['test_name']
    if 'job_keyvals' in view:
        # For a test invocation like:
        # NAME = "dummy_Fail"
        # job.run_test('dummy_Fail', tag='Error', to_throw='TestError')
        # we will:
        # Record a keyval of the jobs test_name field: dummy_Fail
        # On success, yield a tko status with the tagged name:
        #    dummy_Fail.Error
        # On abort, yield a status (not from tko) with the job name:
        #   /build/suite/dummy_Fail.Error
        # Note the last 2 options include the tag. The tag is seperated
        # from the rest of the name with a '.'. The tag or test name can
        # also include a /, and we must isolate the tag before we compare it
        # to the hashed keyval. Based on this we have the following cases:
        # 1. Regular test failure with or without a tag '.': std_job_name is
        #    set to the view test_name, after removing the tag.
        # 2. Regular test Aborts: we know that dynamic_suite inserted a name
        #    like build/suite/test.name (eg:
        #    lumpy-release/R28-3947.0.0/dummy/dummy_Fail.Error), so we
        #    intersect the build/suite/ string we already have with the
        #    test_name in the view. The name of the aborted test is
        #    instrumental in generating the job_name, which is used in
        #    creating a link to the logs.
        # 3. Experimental tests, Aborts and Failures: The test view
        #    corresponding to the afe_job_id of the suite job contains
        #    stubs for each test in this suite. The names of these jobs
        #    will contain an experimental prefix if they were aborted;
        #    If they failed the same names will not contain an experimental
        #    prefix but we would have hashed the name with a prefix. Eg:
        #       Test name = experimental_pass
        #       keyval contains: hash(experimental_pass)
        #       Fail/Pass view['test_name'] = pass
        #       Abort view['test_name'] = board/build/experimental_pass
        #    So we need to add the experimental prefix only if the test was
        #    aborted. Everything else is the same as [2].
        # 4. Experimental server job failures: eg verify passes, something on
        #    the DUT crashes, the experimental server job fails to ssh in. We
        #    need to manually set the experimental flag in this case because the
        #    server job name isn't recorded in the keyvals. For a normal suite
        #    the views will contain: SERVER_JOB, try_new_image, test_name. i.e
        #    the test server jobs should be handled transparently and only the
        #    suite server job should appear in the view. If a server job fails
        #    (for an experimental test or otherwise) we insert the server job
        #    entry into the tko database instead. Put more generally we insert
        #    the last stage we knew about into the db record associated with
        #    that suites afe_job_id. This could lead to a view containing:
        #    SERVER_JOB, try_new_image,
        #    lumpy-release/R28-4008.0.0/bvt/experimental_pass_SERVER_JOB.
        # Neither of these operations will stomp on a pristine string.
        test_name = tools.get_test_name(build, suite, view['test_name'])
        std_job_name = test_name.split('.')[0]

        if (job_status.view_is_for_infrastructure_fail(view) and
            std_job_name.startswith(constants.EXPERIMENTAL_PREFIX)):
                experimental = True

        if std_job_name.startswith(constants.EXPERIMENTAL_PREFIX):
            exp_job_name = std_job_name
        else:
            exp_job_name = constants.EXPERIMENTAL_PREFIX + std_job_name
        std_job_hash = hashlib.md5(std_job_name).hexdigest()
        exp_job_hash = hashlib.md5(exp_job_name).hexdigest()
        raw_test_name_hash = hashlib.md5(raw_test_name).hexdigest()

        # In the experimental abort case both these clauses can evaluate
        # to True.
        if std_job_hash in view['job_keyvals']:
            job_name = view['job_keyvals'][std_job_hash]
        if exp_job_hash in view['job_keyvals']:
            experimental = True
            job_name = view['job_keyvals'][exp_job_hash]
        if raw_test_name_hash in view['job_keyvals']:
            job_name = view['job_keyvals'][raw_test_name_hash]

    # If the name being returned is the test name it needs to include the tag
    return job_name, experimental, std_job_name if not test_name else test_name


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


    def __init__(self, anchor, server, job_string, bug_info=None):
        """Initialize the LogLink by generating the log URL.

        @param anchor      The link text.
        @param server      The hostname of the server this suite ran on.
        @param job_string  The job whose logs we'd like to link to.
        @param bug_info    Info about the bug, if one was filed.
        """
        self.anchor = anchor
        self.url = self._URL_PATTERN % (server, job_string)
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
                anchor_text = "%s (Unknown number of reports)" % (
                        self.anchor.strip())
            elif self.bug_count == 1:
                anchor_text = "%s (new)" % self.anchor.strip()
            else:
                anchor_text = "%s (%s reports)" % (
                        self.anchor.strip(), self.bug_count)
        else:
            url = self.url
            anchor_text = self.anchor.strip()
        return "@@@STEP_LINK@%s@%s@@@"% (anchor_text, url)


    def GenerateTextLink(self):
        """Generate a link to the job's logs, for consumption by a human.

        @return A link formatted for human readability.
        """
        return "%s%s" % (self.anchor, self.url)


class Timings(object):
    """Timings for important events during a suite.

    All timestamps are datetime.datetime objects.

    @var suite_start_time: the time the suite started.
    @var tests_start_time: the time the first test started running.
    """

    # Recorded in create_suite_job as we're staging the components of a
    # build on the devserver. Only the artifacts necessary to start
    # installing images onto DUT's will be staged when we record
    # payload_end_time, the remaining artifacts are downloaded after we kick
    # off the reimaging job, at which point we record artifact_end_time.
    download_start_time = None
    payload_end_time = None
    artifact_end_time = None

    # The test_start_time, but taken off the view that corresponds to the
    # suite instead of an individual test.
    suite_start_time = None

    # Earliest and Latest tests in the set of TestViews passed to us.
    tests_start_time = None
    tests_end_time = None


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

        if job_status.view_is_for_suite_prep(view):
            self.suite_start_time = start_candidate
        else:
            self._UpdateFirstTestStartTime(start_candidate)
            self._UpdateLastTestEndTime(end_candidate)
        if 'job_keyvals' in view:
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


def _full_test_name(job_id, view, build, suite):
    """
    Generates the full test name for printing to logs and generating a link to
    the results.

    @param job_id: the job id.
    @param view: the view for which we are generating the name.
    @param build: the build for this invocation of run_suite.
    @param suite: the suite for this invocation of run_suite.
    @return The test name, possibly with a descriptive prefix appended.
    """
    experimental, test_name = get_view_info(job_id, view, build, suite)[1:]

    # If an experimental test is aborted get_view_info returns a name which
    # includes the prefix.
    prefix = constants.EXPERIMENTAL_PREFIX if (experimental and
        not test_name.startswith(constants.EXPERIMENTAL_PREFIX)) else ''
    return prefix + test_name


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


def main():
    """
    Entry point for run_suite script.
    """
    parser, options, args = parse_options()
    log_name = 'run_suite-default.log'
    if not options.mock_job_id:
        if args:
            print 'Unknown arguments: ' + str(args)
            parser.print_help()
            return
        if not options.build:
            print 'Need to specify which build to use'
            parser.print_help()
            return
        if not options.board:
            print 'Need to specify board'
            parser.print_help()
            return
        if not options.name:
            print 'Need to specify suite name'
            parser.print_help()
            return
        # convert build name from containing / to containing only _
        log_name = 'run_suite-%s.log' % options.build.replace('/', '_')
        log_dir = os.path.join(common.autotest_dir, 'logs')
        if os.path.exists(log_dir):
            log_name = os.path.join(log_dir, log_name)
    if options.num is not None and options.num < 1:
        print 'Number of machines must be more than 0, if specified.'
        parser.print_help()
        return
    if options.no_wait != 'True' and options.no_wait != 'False':
        print 'Please specify "True" or "False" for --no_wait.'
        parser.print_help()
        return
    if options.file_bugs != 'True' and options.file_bugs != 'False':
        print 'Please specify "True" or "False" for --file_bugs.'
        parser.print_help()
        return

    try:
        priority = int(options.priority)
    except ValueError:
        try:
            priority = priorities.Priority.get_value(options.priority)
        except AttributeError:
            print 'Unknown priority level %s.  Try one of %s.' % (
                  options.priority, ', '.join(priorities.Priority.names))

    setup_logging(logfile=log_name)

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
    TKO = frontend_wrappers.RetryingTKO(server=instance_server,
                                        timeout_min=options.afe_timeout_mins,
                                        delay_sec=options.delay_sec)
    logging.info('Started suite job: %s', job_id)

    code = RETURN_CODES.OK
    if wait:
        while not afe.get_jobs(id=job_id, finished=True):
            time.sleep(10)

        views = TKO.run('get_detailed_test_views', afe_job_id=job_id)
        # The intended behavior is to refrain from recording stats if the suite
        # was aborted (either by a user or through the golo rpc). Since all the
        # views associated with the afe_job_id of the suite contain the keyvals
        # of the suite and not the individual tests themselves, we can achieve
        # this without digging through the views.
        is_aborted = any([view['job_keyvals'].get('aborted_by')
                          for view in views])
        # For hostless job in Starting status, there is no test view associated.
        # This can happen when a suite job in Starting status is aborted. When
        # the scheduler hits some limit, e.g., max_hostless_jobs_per_drone,
        # max_jobs_started_per_cycle, a suite job can stays in Starting status.
        if not views:
            code = RETURN_CODES.ERROR
            returnmessage = RETURN_CODES.get_string(code)
            logging.info('\nNo test view was found.\n'
                         'Will return from run_suite with status:  %s',
                         returnmessage)
            return code

        width = max((len(_full_test_name(job_id, view, options.build,
                                         options.name)) for view in views)) + 3

        relevant_views = filter(job_status.view_is_relevant, views)
        if not relevant_views:
            # The main suite job most likely failed in SERVER_JOB.
            relevant_views = views

        timings = Timings()
        web_links = []
        buildbot_links = []
        for view in relevant_views:
            timings.RecordTiming(view)
            if job_status.view_is_for_suite_prep(view):
                view['test_name'] = 'Suite prep'

            job_name, experimental = get_view_info(job_id, view, options.build,
                options.name)[:2]
            test_view = _full_test_name(job_id, view, options.build,
                options.name).ljust(width)
            logging.info("%s%s", test_view, get_pretty_status(view['status']))

            # It's important that we use the test name in the view
            # and not the name returned by full_test_name, as this
            # was the name inserted after the test ran, e.g. for an
            # aborted test full_test_name will return
            # 'experimental_testname' but the view and the bug_id
            # keyval will use '/build/suite/experimental_testname'.
            bug_info = tools.get_test_failure_bug_info(
                    view['job_keyvals'], view['test_name'])

            link = LogLink(test_view, instance_server, job_name, bug_info)
            web_links.append(link)

            # Don't show links on the buildbot waterfall for tests with
            # GOOD status.
            if view['status'] != 'GOOD':
                logging.info("%s  %s: %s", test_view, view['status'],
                             view['reason'])
                if view['status'] == 'TEST_NA':
                    # Didn't run; nothing to do here!
                    continue
                buildbot_links.append(link)
                if code == RETURN_CODES.ERROR:
                    # Failed already, no need to worry further.
                    continue

                # Any non experimental test that has a status other than WARN
                # or GOOD will result in the tree closing. Experimental tests
                # will not close the tree, even if they have been aborted.
                if not experimental:
                    if view['status'] == 'WARN':
                        code = RETURN_CODES.WARNING
                    elif is_fail_status(view['status']):
                        code = RETURN_CODES.ERROR

        # Do not record stats for aborted suites.
        if not is_aborted and not options.mock_job_id:
            timings.SendResultsToStatsd(options.name, options.build,
                                        options.board)
        logging.info(timings)
        logging.info('\n'
                     'Links to test logs:')
        for link in web_links:
            logging.info(link.GenerateTextLink())

        try:
            returnmessage = RETURN_CODES.get_string(code)
        except ValueError:
            returnmessage = 'UNKNOWN'
        logging.info('\n'
                     'Will return from run_suite with status:  %s',
                     returnmessage)

        logging.info('\n'
                     'Output below this line is for buildbot consumption:')
        for link in buildbot_links:
            logging.info(link.GenerateBuildbotLink())
    else:
        logging.info('Created suite job: %r', job_id)
        link = LogLink(options.name, instance_server,
                       '%s-%s' % (job_id, getpass.getuser()))
        logging.info(link.GenerateBuildbotLink())
        logging.info('--no_wait specified; Exiting.')
    return code

if __name__ == "__main__":
    sys.exit(main())
