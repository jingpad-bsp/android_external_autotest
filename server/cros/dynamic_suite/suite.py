# Copyright (c) 2012 The Chromium OS Authors. All rights reserved.
# Use of this source code is governed by a BSD-style license that can be
# found in the LICENSE file.

import hashlib, logging, os, re, traceback

import common

from autotest_lib.client.common_lib import control_data
from autotest_lib.client.common_lib import utils
from autotest_lib.server.cros.dynamic_suite import constants
from autotest_lib.server.cros.dynamic_suite import control_file_getter
from autotest_lib.server.cros.dynamic_suite import frontend_wrappers
from autotest_lib.server.cros.dynamic_suite import job_status
from autotest_lib.server.cros.dynamic_suite.job_status import Status
from autotest_lib.server.cros.dynamic_suite import reporting

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
    def create_from_name(name, build, devserver, cf_getter=None, afe=None,
                         tko=None, pool=None, results_dir=None,
                         max_runtime_mins=24*60,
                         version_prefix=constants.VERSION_PREFIX,
                         file_bugs=False):
        """
        Create a Suite using a predicate based on the SUITE control file var.

        Makes a predicate based on |name| and uses it to instantiate a Suite
        that looks for tests in |autotest_dir| and will schedule them using
        |afe|.  Pulls control files from the default dev server.
        Results will be pulled from |tko| upon completion.

        @param name: a value of the SUITE control file variable to search for.
        @param build: the build on which we're running this suite.
        @param devserver: the devserver which contains the build.
        @param cf_getter: a control_file_getter.ControlFileGetter.
                          If None, default to using a DevServerGetter.
        @param afe: an instance of AFE as defined in server/frontend.py.
        @param tko: an instance of TKO as defined in server/frontend.py.
        @param pool: Specify the pool of machines to use for scheduling
                     purposes.
        @param results_dir: The directory where the job can write results to.
                            This must be set if you want job_id of sub-jobs
                            list in the job keyvals.
        @param max_runtime_mins: Maximum suite runtime, in minutes.
        @param version_prefix: a string, a prefix to be concatenated with the
                               build name to form a label which the DUT needs
                               to be labeled with to be eligible to run this
                               test.
        @param file_bugs: True if we should file bugs on test failures for
                          this suite run.
        @return a Suite instance.
        """
        if cf_getter is None:
            cf_getter = Suite.create_ds_getter(build, devserver)

        return Suite(Suite.name_in_tag_predicate(name),
                     name, build, cf_getter, afe, tko, pool, results_dir,
                     max_runtime_mins, version_prefix, file_bugs)


    @staticmethod
    def create_from_name_and_blacklist(name, blacklist, build, devserver,
                                       cf_getter=None, afe=None, tko=None,
                                       pool=None, results_dir=None,
                                       max_runtime_mins=24*60,
                                       version_prefix=constants.VERSION_PREFIX,
                                       file_bugs=False,
                                       suite_job_id=None):
        """
        Create a Suite using a predicate based on the SUITE control file var.

        Makes a predicate based on |name| and uses it to instantiate a Suite
        that looks for tests in |autotest_dir| and will schedule them using
        |afe|.  Pulls control files from the default dev server.
        Results will be pulled from |tko| upon completion.

        @param name: a value of the SUITE control file variable to search for.
        @param blacklist: iterable of control file paths to skip.
        @param build: the build on which we're running this suite.
        @param devserver: the devserver which contains the build.
        @param cf_getter: a control_file_getter.ControlFileGetter.
                          If None, default to using a DevServerGetter.
        @param afe: an instance of AFE as defined in server/frontend.py.
        @param tko: an instance of TKO as defined in server/frontend.py.
        @param pool: Specify the pool of machines to use for scheduling
                     purposes.
        @param results_dir: The directory where the job can write results to.
                            This must be set if you want job_id of sub-jobs
                            list in the job keyvals.
        @param max_runtime_mins: Maximum suite runtime, in minutes.
        @param version_prefix: a string, a prefix to be concatenated with the
                               build name to form a label which the DUT needs
                               to be labeled with to be eligible to run this
                               test.
        @param file_bugs: True if we should file bugs on test failures for
                          this suite run.
        @param suite_job_id: Job id that will act as parent id to all sub jobs.
                     Default: None
        @return a Suite instance.
        """
        if cf_getter is None:
            cf_getter = Suite.create_ds_getter(build, devserver)

        def in_tag_not_in_blacklist_predicate(test):
            #pylint: disable-msg=C0111
            return (Suite.name_in_tag_predicate(name)(test) and
                    hasattr(test, 'path') and
                    True not in [b.endswith(test.path) for b in blacklist])

        return Suite(in_tag_not_in_blacklist_predicate,
                     name, build, cf_getter, afe, tko, pool, results_dir,
                     max_runtime_mins, version_prefix, file_bugs, suite_job_id)


    def __init__(self, predicate, tag, build, cf_getter, afe=None, tko=None,
                 pool=None, results_dir=None, max_runtime_mins=24*60,
                 version_prefix=constants.VERSION_PREFIX,
                 file_bugs=False, suite_job_id=None):
        """
        Constructor

        @param predicate: a function that should return True when run over a
               ControlData representation of a control file that should be in
               this Suite.
        @param tag: a string with which to tag jobs run in this suite.
        @param build: the build on which we're running this suite.
        @param cf_getter: a control_file_getter.ControlFileGetter
        @param afe: an instance of AFE as defined in server/frontend.py.
        @param tko: an instance of TKO as defined in server/frontend.py.
        @param pool: Specify the pool of machines to use for scheduling
                purposes.
        @param results_dir: The directory where the job can write results to.
                            This must be set if you want job_id of sub-jobs
                            list in the job keyvals.
        @param max_runtime_mins: Maximum suite runtime, in minutes.
        @param version_prefix: a string, prefix for the database label
                               associated with the build
        @param suite_job_id: Job id that will act as parent id to all sub jobs.
                             Default: None
        """
        self._predicate = predicate
        self._tag = tag
        self._build = build
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
                                                 add_experimental=True)
        self._max_runtime_mins = max_runtime_mins
        self._version_prefix = version_prefix
        self._file_bugs = file_bugs
        self._suite_job_id = suite_job_id


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
        job_deps = list(test.dependencies)
        if self._pool:
            meta_hosts = self._pool
            cros_label = self._version_prefix + self._build
            job_deps.append(cros_label)
        else:
            # No pool specified use any machines with the following label.
            meta_hosts = self._version_prefix + self._build
        test_obj = self._afe.create_job(
            control_file=test.text,
            name='/'.join([self._build, self._tag, test.name]),
            control_type=test.test_type.capitalize(),
            meta_hosts=[meta_hosts],
            dependencies=job_deps,
            keyvals={constants.JOB_BUILD_KEY: self._build,
                     constants.JOB_SUITE_KEY: self._tag},
            max_runtime_mins=self._max_runtime_mins,
            parent_job_id=self._suite_job_id,
            test_retry=test.retries)

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
        """
        logging.debug('Discovered %d stable tests.', len(self.stable_tests()))
        logging.debug('Discovered %d unstable tests.',
                      len(self.unstable_tests()))

        Status('INFO', 'Start %s' % self._tag).record_result(record)
        try:
            for test in self.stable_tests():
                logging.debug('Scheduling %s', test.name)
                self._jobs.append(self._create_job(test))

            if add_experimental:
                for test in self.unstable_tests():
                    logging.debug('Scheduling experimental %s', test.name)
                    test.name = constants.EXPERIMENTAL_PREFIX + test.name
                    self._jobs.append(self._create_job(test))

            if self._results_dir:
                self._remember_scheduled_job_ids()
        except Exception:  # pylint: disable=W0703
            logging.error(traceback.format_exc())
            Status('FAIL', self._tag,
                   'Exception while scheduling suite').record_result(record)


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
            for result in job_status.wait_for_results(self._afe,
                                                      self._tko,
                                                      self._jobs):
                result.record_all(record)
                if (self._results_dir and
                    job_status.is_for_infrastructure_fail(result)):
                    self._remember_provided_job_id(result)

                # I'd love to grab the actual tko test object here, as that
                # includes almost all of the needed information: test name,
                # status, reason, etc. However, doing so would cause a
                # bunch of database traffic to grab data that we already
                # have laying around in memory across several objects here.
                worse = result.is_worse_than(job_status.Status("WARN", ""))
                if self._file_bugs and worse:
                    failure = reporting.TestFailure(build=self._build,
                                                    suite=self._tag,
                                                    test=result.test_name,
                                                    reason=result.reason,
                                                    owner=result.owner,
                                                    hostname=result.hostname,
                                                    job_id=result.id)

                    bug_reporter.report(failure, bug_template)
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


    @staticmethod
    def find_and_parse_tests(cf_getter, predicate, add_experimental=False):
        """
        Function to scan through all tests and find eligible tests.

        Looks at control files returned by _cf_getter.get_control_file_list()
        for tests that pass self._predicate().

        @param cf_getter: a control_file_getter.ControlFileGetter used to list
               and fetch the content of control files
        @param predicate: a function that should return True when run over a
               ControlData representation of a control file that should be in
               this Suite.
        @param add_experimental: add tests with experimental attribute set.

        @return list of ControlData objects that should be run, with control
                file text added in |text| attribute. Results are sorted based
                on the TIME setting in control file, slowest test comes first.
        """
        tests = {}
        files = cf_getter.get_control_file_list()
        matcher = re.compile(r'[^/]+/(deps|profilers)/.+')
        for file in filter(lambda f: not matcher.match(f), files):
            logging.debug('Considering %s', file)
            text = cf_getter.get_control_file_contents(file)
            try:
                found_test = control_data.parse_control_string(
                        text, raise_warnings=True)
                if not add_experimental and found_test.experimental:
                    continue

                found_test.text = text
                found_test.path = file
                tests[file] = found_test
            except control_data.ControlVariableException, e:
                logging.warn("Skipping %s\n%s", file, e)
            except Exception, e:
                logging.error("Bad %s\n%s", file, e)
        tests = [test for test in tests.itervalues() if predicate(test)]
        tests.sort(key=lambda t:
                   control_data.ControlData.get_test_time_index(t.time),
                   reverse=True)
        return tests
