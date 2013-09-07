# Copyright (c) 2012 The Chromium OS Authors. All rights reserved.
# Use of this source code is governed by a BSD-style license that can be
# found in the LICENSE file.

import datetime, hashlib, logging, os, re, traceback

import common

from autotest_lib.client.common_lib import control_data
from autotest_lib.client.common_lib import priorities
from autotest_lib.client.common_lib import site_utils, utils, error
from autotest_lib.server.cros.dynamic_suite import constants
from autotest_lib.server.cros.dynamic_suite import control_file_getter
from autotest_lib.server.cros.dynamic_suite import frontend_wrappers
from autotest_lib.server.cros.dynamic_suite import job_status
from autotest_lib.server.cros.dynamic_suite import reporting
from autotest_lib.server.cros.dynamic_suite import tools
from autotest_lib.server.cros.dynamic_suite.job_status import Status

class Suite(object):
    """
    A suite of tests, defined by some predicate over control file variables.

    Given a place to search for control files a predicate to match the desired
    tests, can gather tests and fire off jobs to run them, and then wait for
    results.

    @var _predicate: a function that should return True when run over a
         ControlData representation of a control file that should be in
         this Suite.
    @var _tag: a string with which to tag jobs run in this suite.
    @var _build: the build on which we're running this suite.
    @var _afe: an instance of AFE as defined in server/frontend.py.
    @var _tko: an instance of TKO as defined in server/frontend.py.
    @var _jobs: currently scheduled jobs, if any.
    @var _cf_getter: a control_file_getter.ControlFileGetter
    """


    @staticmethod
    def create_ds_getter(build, devserver):
        """
        @param build: the build on which we're running this suite.
        @param devserver: the devserver which contains the build.
        @return a FileSystemGetter instance that looks under |autotest_dir|.
        """
        return control_file_getter.DevServerGetter(build, devserver)


    @staticmethod
    def create_fs_getter(autotest_dir):
        """
        @param autotest_dir: the place to find autotests.
        @return a FileSystemGetter instance that looks under |autotest_dir|.
        """
        # currently hard-coded places to look for tests.
        subpaths = ['server/site_tests', 'client/site_tests',
                    'server/tests', 'client/tests']
        directories = [os.path.join(autotest_dir, p) for p in subpaths]
        return control_file_getter.FileSystemGetter(directories)


    @staticmethod
    def parse_tag(tag):
        """Splits a string on ',' optionally surrounded by whitespace.
        @param tag: string to split.
        """
        return map(lambda x: x.strip(), tag.split(','))


    @staticmethod
    def name_in_tag_predicate(name):
        """Returns predicate that takes a control file and looks for |name|.

        Builds a predicate that takes in a parsed control file (a ControlData)
        and returns True if the SUITE tag is present and contains |name|.

        @param name: the suite name to base the predicate on.
        @return a callable that takes a ControlData and looks for |name| in that
                ControlData object's suite member.
        """
        return lambda t: hasattr(t, 'suite') and \
                         name in Suite.parse_tag(t.suite)


    @staticmethod
    def not_in_blacklist_predicate(blacklist):
        """Returns predicate that takes a control file and looks for its
        path to not be in given blacklist.

        @param blacklist: A list of strings both paths on control_files that
                          should be blacklisted.

        @return a callable that takes a ControlData and looks for it to be
                absent from blacklist.
        """
        return lambda t: hasattr(t, 'path') and \
                         not any(b.endswith(t.path) for b in blacklist)


    @staticmethod
    def test_name_equals_predicate(test_name):
        """Returns predicate that matched based on a test's name.

        Builds a predicate that takes in a parsed control file (a ControlData)
        and returns True if the test name is equal to |test_name|.

        @param test_name: the test name to base the predicate on.
        @return a callable that takes a ControlData and looks for |test_name|
                in that ControlData's name.
        """
        return lambda t: hasattr(t, 'name') and test_name == t.name


    @staticmethod
    def test_name_matches_pattern_predicate(test_name_pattern):
        """Returns predicate that matches based on a test's name pattern.

        Builds a predicate that takes in a parsed control file (a ControlData)
        and returns True if the test name matches the given regular expression.

        @param test_name_pattern: regular expression (string) to match against
                                  test names.
        @return a callable that takes a ControlData and returns
                True if the name fields matches the pattern.
        """
        return lambda t: hasattr(t, 'name') and re.match(test_name_pattern,
                                                         t.name)


    @staticmethod
    def test_file_matches_pattern_predicate(test_file_pattern):
        """Returns predicate that matches based on a test's file name pattern.

        Builds a predicate that takes in a parsed control file (a ControlData)
        and returns True if the test's control file name matches the given
        regular expression.

        @param test_file_pattern: regular expression (string) to match against
                                  control file names.
        @return a callable that takes a ControlData and and returns
                True if control file name matches the pattern.
        """
        return lambda t: hasattr(t, 'path') and re.match(test_file_pattern,
                                                         t.path)


    @staticmethod
    def list_all_suites(build, devserver, cf_getter=None):
        """
        Parses all ControlData objects with a SUITE tag and extracts all
        defined suite names.

        @param build: the build on which we're running this suite.
        @param devserver: the devserver which contains the build.
        @param cf_getter: control_file_getter.ControlFileGetter. Defaults to
                          using DevServerGetter.

        @return list of suites
        """
        if cf_getter is None:
            cf_getter = Suite.create_ds_getter(build, devserver)

        suites = set()
        predicate = lambda t: hasattr(t, 'suite')
        for test in Suite.find_and_parse_tests(cf_getter, predicate,
                                               add_experimental=True):
            suites.update(Suite.parse_tag(test.suite))
        return list(suites)


    @staticmethod
    def create_from_predicates(predicates, build, board, devserver,
                               cf_getter=None, name='ad_hoc_suite', **dargs):
        """
        Create a Suite using a given predicate test filters.

        Uses supplied predicate(s) to instantiate a Suite. Looks for tests in
        |autotest_dir| and will schedule them using |afe|.  Pulls control files
        from the default dev server. Results will be pulled from |tko| upon
        completion.

        @param predicates: A list of callables that accept ControlData
                           representations of control files. A test will be
                           included in suite if all callables in this list
                           return True on the given control file.
        @param build: the build on which we're running this suite.
        @param board: the board on which we're running this suite.
        @param devserver: the devserver which contains the build.
        @param cf_getter: control_file_getter.ControlFileGetter. Defaults to
                          using DevServerGetter.
        @param name: name of suite. Defaults to 'ad_hoc_suite'
        @param **dargs: Any other Suite constructor parameters, as described
                        in Suite.__init__ docstring.
        @return a Suite instance.
        """
        if cf_getter is None:
            cf_getter = Suite.create_ds_getter(build, devserver)

        return Suite(predicates,
                     name, build, board, cf_getter, **dargs)


    @staticmethod
    def create_from_name(name, build, board, devserver, cf_getter=None,
                         **dargs):
        """
        Create a Suite using a predicate based on the SUITE control file var.

        Makes a predicate based on |name| and uses it to instantiate a Suite
        that looks for tests in |autotest_dir| and will schedule them using
        |afe|.  Pulls control files from the default dev server.
        Results will be pulled from |tko| upon completion.

        @param name: a value of the SUITE control file variable to search for.
        @param build: the build on which we're running this suite.
        @param board: the board on which we're running this suite.
        @param devserver: the devserver which contains the build.
        @param cf_getter: control_file_getter.ControlFileGetter. Defaults to
                          using DevServerGetter.
        @param **dargs: Any other Suite constructor parameters, as described
                        in Suite.__init__ docstring.
        @return a Suite instance.
        """
        if cf_getter is None:
            cf_getter = Suite.create_ds_getter(build, devserver)

        return Suite([Suite.name_in_tag_predicate(name)],
                     name, build, board, cf_getter, **dargs)


    def __init__(self, predicates, tag, build, board, cf_getter, afe=None,
                 tko=None, pool=None, results_dir=None, max_runtime_mins=24*60,
                 timeout=24, file_bugs=False, file_experimental_bugs=False,
                 suite_job_id=None, ignore_deps=False, extra_deps=[],
                 priority=priorities.Priority.DEFAULT):
        """
        Constructor

        @param predicates: A list of callables that accept ControlData
                           representations of control files. A test will be
                           included in suite is all callables in this list
                           return True on the given control file.
        @param tag: a string with which to tag jobs run in this suite.
        @param build: the build on which we're running this suite.
        @param board: the board on which we're running this suite.
        @param cf_getter: a control_file_getter.ControlFileGetter
        @param afe: an instance of AFE as defined in server/frontend.py.
        @param tko: an instance of TKO as defined in server/frontend.py.
        @param pool: Specify the pool of machines to use for scheduling
                purposes.
        @param results_dir: The directory where the job can write results to.
                            This must be set if you want job_id of sub-jobs
                            list in the job keyvals.
        @param max_runtime_mins: Maximum suite runtime, in minutes.
        @param timeout: Maximum job lifetime, in hours.
        @param suite_job_id: Job id that will act as parent id to all sub jobs.
                             Default: None
        @param ignore_deps: True if jobs should ignore the DEPENDENCIES
                            attribute and skip applying of dependency labels.
                            (Default:False)
        @param extra_deps: A list of strings which are the extra DEPENDENCIES
                           to add to each test being scheduled.
        @param priority: Integer priority level.  Higher is more important.

        """
        def combined_predicate(test):
            #pylint: disable-msg=C0111
            return all((f(test) for f in predicates))
        self._predicate = combined_predicate

        self._tag = tag
        self._build = build
        self._board = board
        self._cf_getter = cf_getter
        self._results_dir = results_dir
        self._afe = afe or frontend_wrappers.RetryingAFE(timeout_min=30,
                                                         delay_sec=10,
                                                         debug=False)
        self._tko = tko or frontend_wrappers.RetryingTKO(timeout_min=30,
                                                         delay_sec=10,
                                                         debug=False)
        self._pool = pool
        self._jobs = []
        self._tests = Suite.find_and_parse_tests(self._cf_getter,
                                                 self._predicate,
                                                 self._tag,
                                                 add_experimental=True)
        self._max_runtime_mins = max_runtime_mins
        self._timeout = timeout
        self._file_bugs = file_bugs
        self._file_experimental_bugs = file_experimental_bugs
        self._suite_job_id = suite_job_id
        self._ignore_deps = ignore_deps
        self._extra_deps = extra_deps
        self._priority = priority


    @property
    def tests(self):
        """
        A list of ControlData objects in the suite, with added |text| attr.
        """
        return self._tests


    def stable_tests(self):
        """
        |self.tests|, filtered for non-experimental tests.
        """
        return filter(lambda t: not t.experimental, self.tests)


    def unstable_tests(self):
        """
        |self.tests|, filtered for experimental tests.
        """
        return filter(lambda t: t.experimental, self.tests)


    def _create_job(self, test):
        """
        Thin wrapper around frontend.AFE.create_job().

        @param test: ControlData object for a test to run.
        @return a frontend.Job object with an added test_name member.
                test_name is used to preserve the higher level TEST_NAME
                name of the job.
        """
        if self._ignore_deps:
            job_deps = []
        else:
            job_deps = list(test.dependencies)

        if self._extra_deps:
            job_deps.extend(self._extra_deps)
        if self._pool:
            job_deps.append(self._pool)

        test_obj = self._afe.create_job(
            control_file=test.text,
            name='/'.join([self._build, self._tag, test.name]),
            control_type=test.test_type.capitalize(),
            meta_hosts=[self._board],
            dependencies=job_deps,
            keyvals={constants.JOB_BUILD_KEY: self._build,
                     constants.JOB_SUITE_KEY: self._tag},
            max_runtime_mins=self._max_runtime_mins,
            timeout=self._timeout,
            parent_job_id=self._suite_job_id,
            test_retry=test.retries,
            priority=self._priority)

        setattr(test_obj, 'test_name', test.name)

        return test_obj


    def schedule_and_wait(self, record, add_experimental=True):
        """
        Synchronously run tests in |self.tests|.

        See |schedule| and |wait| for more information.

        Schedules tests against a device running image |self._build|, and
        then polls for status, using |record| to print status when each
        completes.

        Tests returned by self.stable_tests() will always be run, while tests
        in self.unstable_tests() will only be run if |add_experimental| is true.

        @param record: callable that records job status.
                 prototype:
                   record(base_job.status_log_entry)
        @param manager: a populated HostLockManager instance to handle
                        unlocking DUTs that we already reimaged.
        @param add_experimental: schedule experimental tests as well, or not.
        """
        # This method still exists for unittesting convenience.
        self.schedule(record, add_experimental)
        self.wait(record)


    def schedule(self, record, add_experimental=True):
        #pylint: disable-msg=C0111
        """
        Schedule jobs using |self._afe|.

        frontend.Job objects representing each scheduled job will be put in
        |self._jobs|.

        @param add_experimental: schedule experimental tests as well, or not.
        @returns: The number of tests that were scheduled.
        """
        logging.debug('Discovered %d stable tests.', len(self.stable_tests()))
        logging.debug('Discovered %d unstable tests.',
                      len(self.unstable_tests()))
        n_scheduled = 0

        begin_time_str = datetime.datetime.now().strftime(job_status.TIME_FMT)
        Status('INFO', 'Start %s' % self._tag).record_result(record)
        try:
            tests = self.stable_tests()
            if add_experimental:
                for test in self.unstable_tests():
                    test.name = constants.EXPERIMENTAL_PREFIX + test.name
                    tests.append(test)

            for test in tests:
                logging.debug('Scheduling %s', test.name)
                try:
                    job = self._create_job(test)
                except error.NoEligibleHostException:
                    logging.debug('%s not applicable for this board/pool. '
                                  'Emitting TEST_NA.', test.name)
                    Status('TEST_NA', test.name, 'Unsatisfiable DEPENDENCIES',
                           begin_time_str=begin_time_str).record_all(record)
                else:
                    self._jobs.append(job)
                    n_scheduled += 1

            if self._results_dir:
                self._remember_scheduled_job_ids()
        except Exception:  # pylint: disable=W0703
            logging.error(traceback.format_exc())
            Status('FAIL', self._tag,
                   'Exception while scheduling suite').record_result(record)

        return n_scheduled


    def should_file_bug(self, result):
        """
        Returns True if this failure requires a bug.

        @param result: A result, encapsulating the status of the failed job.
        @return: True if we should file bugs for this failure.
        """
        is_not_experimental = (
            constants.EXPERIMENTAL_PREFIX not in result._test_name and
            constants.EXPERIMENTAL_PREFIX not in result._job_name)

        return (self._file_bugs and
                (is_not_experimental or self._file_experimental_bugs) and
                result.is_worse_than(job_status.Status('WARN', '', 'reason')))


    def wait(self, record, bug_template={}):
        """
        Polls for the job statuses, using |record| to print status when each
        completes.

        @param record: callable that records job status.
                 prototype:
                   record(base_job.status_log_entry)
        @param bug_template: A template dictionary specifying the default bug
                             filing options for failures in this suite.
        """
        if self._file_bugs:
            bug_reporter = reporting.Reporter()
        try:
            if self._suite_job_id:
                results_generator = job_status.wait_for_child_results(
                        self._afe, self._tko, self._suite_job_id)
            else:
                logging.warn('Unknown suite_job_id, falling back to less '
                             'efficient results_generator.')
                results_generator = job_status.wait_for_results(self._afe,
                                                                self._tko,
                                                                self._jobs)
            for result in results_generator:
                result.record_all(record)
                if (self._results_dir and
                    job_status.is_for_infrastructure_fail(result)):
                    self._remember_provided_job_id(result)
                elif (self._results_dir and isinstance(result, Status)):
                    self._remember_test_status_job_id(result)

                if self.should_file_bug(result):
                    job_views = self._tko.run('get_detailed_test_views',
                                              afe_job_id=result.id)

                    failure = reporting.TestFailure(self._build,
                            site_utils.get_chrome_version(job_views),
                            self._tag,
                            result)

                    bug_info = bug_reporter.report(failure, bug_template)
                    bug_keyvals = tools.create_bug_keyvals(
                            result.test_name, bug_info)
                    try:
                        utils.write_keyval(self._results_dir, bug_keyvals)
                    except ValueError:
                        logging.error('Unable to log keyval for test:%s '
                                      'bugid: %s', result.test_name, bug_id)

        except Exception:  # pylint: disable=W0703
            logging.error(traceback.format_exc())
            Status('FAIL', self._tag,
                   'Exception waiting for results').record_result(record)


    def abort(self):
        """
        Abort all scheduled test jobs.
        """
        if self._jobs:
            job_ids = [job.id for job in self._jobs]
            self._afe.run('abort_host_queue_entries', job__id__in=job_ids)


    def _remember_scheduled_job_ids(self):
        """
        Record scheduled job ids as keyvals, so they can be referenced later.
        """
        for job in self._jobs:
            self._remember_provided_job_id(job)


    def _remember_provided_job_id(self, job):
        """
        Record provided job as a suite job keyval, for later referencing.

        @param job: some representation of a job, including id, test_name
                    and owner
        """
        if job.id and job.owner and job.test_name:
            job_id_owner = '%s-%s' % (job.id, job.owner)
            logging.debug('Adding job keyval for %s=%s',
                          job.test_name, job_id_owner)
            utils.write_keyval(
                self._results_dir,
                {hashlib.md5(job.test_name).hexdigest(): job_id_owner})


    def _remember_test_status_job_id(self, status):
        """
        Record provided status as a test status keyval, for later referencing.

        @param status: Test status, including properties such as id, test_name
                       and owner.
        """
        if status.id and status.owner and status.test_name:
            test_id_owner = '%s-%s' % (status.id, status.owner)
            logging.debug('Adding status keyval for %s=%s',
                          status.test_name, test_id_owner)
            utils.write_keyval(
                self._results_dir,
                {hashlib.md5(status.test_name).hexdigest(): test_id_owner})


    @staticmethod
    def find_and_parse_tests(cf_getter, predicate, suite_name='',
                             add_experimental=False):
        """
        Function to scan through all tests and find eligible tests.

        Looks at control files returned by _cf_getter.get_control_file_list()
        for tests that pass self._predicate(). When this method is called
        with a file system ControlFileGetter, it performs a full parse of the
        root directory associated with the getter. This is the case when it's
        invoked from suite_preprocessor. When it's invoked with a devserver
        getter it looks up the suite_name in a suite to control file map
        generated at build time, and parses the relevant control files alone.
        This lookup happens on the devserver, so as far as this method is
        concerned, both cases are equivalent.

        @param cf_getter: a control_file_getter.ControlFileGetter used to list
               and fetch the content of control files
        @param predicate: a function that should return True when run over a
               ControlData representation of a control file that should be in
               this Suite.
        @param suite_name: If specified, this method will attempt to restrain
                           the search space to just this suite's control files.
        @param add_experimental: add tests with experimental attribute set.

        @return list of ControlData objects that should be run, with control
                file text added in |text| attribute. Results are sorted based
                on the TIME setting in control file, slowest test comes first.
        """
        tests = {}
        files = cf_getter.get_control_file_list(suite_name=suite_name)

        matcher = re.compile(r'[^/]+/(deps|profilers)/.+')
        parsed_count = 0
        for file in filter(lambda f: not matcher.match(f), files):
            text = cf_getter.get_control_file_contents(file)
            try:
                found_test = control_data.parse_control_string(
                        text, raise_warnings=True)
                parsed_count += 1
                if not add_experimental and found_test.experimental:
                    continue
                found_test.text = text
                found_test.path = file
                tests[file] = found_test
            except control_data.ControlVariableException, e:
                logging.warn("Skipping %s\n%s", file, e)
            except Exception, e:
                logging.error("Bad %s\n%s", file, e)
        logging.debug('Parsed %s control files.', parsed_count)
        tests = [test for test in tests.itervalues() if predicate(test)]
        tests.sort(key=lambda t:
                   control_data.ControlData.get_test_time_index(t.time),
                   reverse=True)
        return tests
