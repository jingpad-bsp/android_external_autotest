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

import getpass, hashlib, logging, optparse, os, time, sys
from datetime import datetime

import common

from autotest_lib.client.common_lib import global_config, error, utils
from autotest_lib.server.cros.dynamic_suite import constants
from autotest_lib.server.cros.dynamic_suite import frontend_wrappers
from autotest_lib.server.cros.dynamic_suite import job_status
from autotest_lib.server.cros.dynamic_suite.reimager import Reimager
from autotest_lib.site_utils.graphite import stats

CONFIG = global_config.global_config

# Return code that will be sent back to autotest_rpc_server.py
OK = 0
ERROR = 1
WARNING = 2


def setup_logging(logfile=None):
    """Setup basic logging with all logging info stripped.

    Calls to logging will only show the message. No severity is logged.

    @param logfile: If specified dump output to a file as well.
    """
    screen_handler = logging.StreamHandler()
    screen_handler.setFormatter(logging.Formatter('%(message)s'))
    logging.getLogger().addHandler(screen_handler)
    logging.getLogger().setLevel(logging.INFO)
    if logfile:
        file_handler = logging.FileHandler(logfile)
        file_handler.setLevel(logging.DEBUG)
        logging.getLogger().addHandler(file_handler)


def parse_options():
    """ Parse command line options. """

    usage = "usage: %prog [options]"
    parser = optparse.OptionParser(usage=usage)
    parser.add_option("-b", "--board", dest="board")
    parser.add_option("-i", "--build", dest="build")
    #  This should just be a boolean flag, but the autotest "proxy" code
    #  can't handle flags that don't take arguments.
    parser.add_option("-n", "--no_wait", dest="no_wait", default="False",
                      help='Must pass "True" or "False" if used.')
    parser.add_option("-p", "--pool", dest="pool", default=None)
    parser.add_option("-s", "--suite_name", dest="name")
    parser.add_option("-t", "--timeout_min", dest="timeout_min", default=30)
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

    options, args = parser.parse_args()
    return parser, options, args


def get_pretty_status(status):
    """
    Buckets input status into either passed, info or failed.

    @param status: Status message to bucket.
    @return: A string representing the bucket we place
             the input status in.
    """
    if status == 'GOOD':
        return '[ PASSED ]'
    elif status == 'TEST_NA':
        return '[  INFO  ]'
    return '[ FAILED ]'

def is_fail_status(status):
    """
    Checks if the input status falls into the failure bucket.

    @param status: Status message to bucket.
    @return: True if the input status represents a failure.
    """
    # All the statuses tests can have when they fail.
    if status in ['FAIL', 'ERROR']:
        return True
    return False


def get_view_info(suite_job_id, view):
    """
    Parse a view for the slave job name and job_id.

    @param suite_job_id: The job id of our master suite job.
    @param view: Test result view.
    @return A tuple job_name, experimental of the slave test run
            described by view.
    """
    # By default, we are the main suite job since there is no
    # keyval entry for our job_name.
    job_name = '%s-%s' % (suite_job_id, getpass.getuser())
    experimental = False
    if 'job_keyvals' in view:
        # The job name depends on whether it's experimental or not.
        if view['test_name'].startswith(Reimager.JOB_NAME):
            std_job_name = Reimager.JOB_NAME
        elif job_status.view_is_for_infrastructure_fail(view):
            std_job_name = view['test_name']
        else:
            std_job_name = view['test_name'].split('.')[0]
        exp_job_name = constants.EXPERIMENTAL_PREFIX + std_job_name

        std_job_hash = hashlib.md5(std_job_name).hexdigest()
        exp_job_hash = hashlib.md5(exp_job_name).hexdigest()

        if std_job_hash in view['job_keyvals']:
            job_name = view['job_keyvals'][std_job_hash]
        elif exp_job_hash in view['job_keyvals']:
            experimental = True
            job_name = view['job_keyvals'][exp_job_hash]

        # For backward compatibility.
        if std_job_name in view['job_keyvals']:
            job_name = view['job_keyvals'][std_job_name]
        elif exp_job_name in view['job_keyvals']:
            experimental = True
            job_name = view['job_keyvals'][exp_job_name]

    return job_name, experimental


class LogLink(object):
    """
    Link to a log.

    @var anchor: the link text.
    @var url: the link url.
    """
    def __init__(self, anchor, job_string):
        """
        Initialize the LogLink by generating the log URL.

        @param anchor: the link text.
        @param job_string: the job whose logs we'd like to link to.
        """
        self.anchor = anchor
        host = CONFIG.get_config_value('SERVER', 'hostname', type=str)
        pattern = CONFIG.get_config_value('CROS', 'log_url_pattern', type=str)
        self.url = pattern % (host, job_string)


    def GenerateBuildbotLink(self):
        """
        Generate a link to the job's logs, for consumption by buildbot.

        @return A link formatted for the buildbot log annotator.
        """
        return "@@@STEP_LINK@%s@%s@@@" % (self.anchor.strip(), self.url)


    def GenerateTextLink(self):
        """
        Generate a link to the job's logs, for consumption by a human.

        @return A link formatted for human readability.
        """
        return "%s%s" % (self.anchor, self.url)


class Timings(object):
    """Timings for important events during a suite.

    All timestamps are datetime.datetime objects.

    @var suite_start_time: the time the suite started.
    @var reimage_start_time: the time we started reimaging devices.
    @var reimage_end_time: the time we finished reimaging devices.
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

    # reimaging_times is a dictionary mapping a host name to it's start and
    # end reimage timings. RecordTiming is invoked with test views, that
    # correspond to tests in a suite; these tests might've run across
    # different hosts. Each view that RecordTiming is invoked with creates a
    # new entry in reimaging_times; When it's time to log reimage timings we
    # iterate over this dict and create a reimaging_info string. This is a
    # one time operation and only happens after all the TestViews in a suite
    # are added to the reimaging_times dictionary.
    # reimaging_times eg: {'hostname': (start_time, end_time)}
    reimage_times = {}

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
        elif view['test_name'].startswith(Reimager.JOB_NAME):
            if '-' in view['test_name']:
                hostname = view['test_name'].split('-', 1)[1]
            else:
                hostname = ''
            self.reimage_times[hostname] = (start_candidate, end_candidate)
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
        reimaging_info = ''
        for host, (start, end) in self.reimage_times.iteritems():
            reimaging_info += ('Reimaging %s started at %s\n'
                               'Reimaging %s ended at %s\n' % (host, start,
                                                               host, end))
        return ('\n'
                'Suite timings:\n'
                'Downloads started at %s\n'
                'Payload downloads ended at %s\n'
                'Suite started at %s\n'
                '%s'
                'Artifact downloads ended (at latest) at %s\n'
                'Testing started at %s\n'
                'Testing ended at %s\n' % (self.download_start_time,
                                           self.payload_end_time,
                                           self.suite_start_time,
                                           reimaging_info,
                                           self.artifact_end_time,
                                           self.tests_start_time,
                                           self.tests_end_time))

    def SendResultsToStatsd(self, suite, build, board):
        """
        Sends data to statsd.

        1. Makes a data_key of the form: run_suite.$board.$branch.$suite
            eg: stats/gauges/<hostname>/run_suite/<board>/<branch>/<suite>/
        2. Computes timings for several start and end event pairs.
        3. Computes timings for reimage events for all hosts.
        4. Sends all timing values to statsd.

        @param suite: scheduled suite that we want to record the results of.
        @param build: the build that this suite ran on.
                      eg: 'lumpy-release/R26-3570.0.0'
        @param board: the board that this suite ran on.
        """
        data_key_dict = {
            'board': board,
            'branch': build[build.find('/')+1:build.rfind('-')],
            'suite': suite,
        }
        data_key = 'run_suite.%(board)s.%(branch)s.%(suite)s' % data_key_dict

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

        for host, (start, end) in self.reimage_times.iteritems():
            if start and end:
                stats.Timer(data_key).send(host.replace('.', '_'),
                    (end - start).total_seconds())


def _full_test_name(job_id, view):
    """Generates the full test name for printing to logs.

    @param job_id: the job id.
    @param view: the view for which we are generating the name.
    @return The test name, possibly with a descriptive prefix appended.
    """
    job_name, experimental = get_view_info(job_id, view)
    prefix = constants.EXPERIMENTAL_PREFIX if experimental else ''
    return prefix + view['test_name']


def main():
    """ Main method of run_suites. """
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
    setup_logging(logfile=log_name)

    try:
        if not options.bypass_labstatus:
            utils.check_lab_status(options.board)
    except (error.LabIsDownException, error.BoardIsDisabledException) as e:
        logging.debug('Error Message: %s', e)
        print str(e)
        return WARNING

    afe = frontend_wrappers.RetryingAFE(timeout_min=options.timeout_min,
                                        delay_sec=options.delay_sec)

    wait = (options.no_wait == 'False')
    file_bugs = (options.file_bugs == 'True')
    if options.mock_job_id:
        job_id = int(options.mock_job_id)
    else:
        job_id = afe.run('create_suite_job', suite_name=options.name,
                         board=options.board, build=options.build,
                         check_hosts=wait, pool=options.pool, num=options.num,
                         file_bugs=file_bugs)
    TKO = frontend_wrappers.RetryingTKO(timeout_min=options.timeout_min,
                                        delay_sec=options.delay_sec)
    logging.info('Started suite job: %s', job_id)

    code = OK
    while wait and True:
        if not afe.get_jobs(id=job_id, finished=True):
            time.sleep(1)
            continue
        views = TKO.run('get_detailed_test_views', afe_job_id=job_id)
        width = max((len(_full_test_name(job_id, view)) for view in views)) + 3

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

            job_name, experimental = get_view_info(job_id, view)
            test_view = _full_test_name(job_id, view).ljust(width)
            logging.info("%s%s", test_view, get_pretty_status(view['status']))
            link = LogLink(test_view, job_name)
            web_links.append(link)

            if view['status'] != 'GOOD':
                logging.info("%s  %s: %s", test_view, view['status'],
                             view['reason'])
                # Don't show links on the buildbot waterfall for tests with
                # GOOD status.
                buildbot_links.append(link)
                if view['status'] == 'TEST_NA':
                    # Didn't run; nothing to do here!
                    continue
                if code == ERROR:
                    # Failed already, no need to worry further.
                    continue
                if (view['status'] == 'WARN' or
                    (is_fail_status(view['status']) and experimental)):
                    # Failures that produce a warning. Either a test with WARN
                    # status or any experimental test failure.
                    code = WARNING
                else:
                    code = ERROR

        timings.SendResultsToStatsd(options.name, options.build, options.board)
        logging.info(timings)
        logging.info('\n'
                     'Links to test logs:')
        for link in web_links:
            logging.info(link.GenerateTextLink())
        logging.info('\n'
                     'Output below this line is for buildbot consumption:')
        for link in buildbot_links:
            logging.info(link.GenerateBuildbotLink())
        break
    else:
        logging.info('Created suite job: %r', job_id)
        link = LogLink(options.name, '%s-%s' % (job_id, getpass.getuser()))
        logging.info(link.GenerateBuildbotLink())
        logging.info('--no_wait specified; Exiting.')
    return code

if __name__ == "__main__":
    sys.exit(main())
