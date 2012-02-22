# Copyright (c) 2012 The Chromium OS Authors. All rights reserved.
# Use of this source code is governed by a BSD-style license that can be
# found in the LICENSE file.

import common
import compiler, logging, os, random, re, time
from autotest_lib.client.common_lib import control_data, global_config, error
from autotest_lib.client.common_lib import utils
from autotest_lib.client.common_lib.cros import dev_server
from autotest_lib.server.cros import control_file_getter, frontend_wrappers
from autotest_lib.server import frontend


VERSION_PREFIX = 'cros-version:'
CONFIG = global_config.global_config


def inject_vars(vars, control_file_in):
    """
    Inject the contents of |vars| into |control_file_in|

    @param vars: a dict to shoehorn into the provided control file string.
    @param control_file_in: the contents of a control file to munge.
    @return the modified control file string.
    """
    control_file = ''
    for key, value in vars.iteritems():
        control_file += "%s='%s'\n" % (key, value)
    return control_file + control_file_in


def _image_url_pattern():
    return CONFIG.get_config_value('CROS', 'image_url_pattern', type=str)


def _package_url_pattern():
    return CONFIG.get_config_value('CROS', 'package_url_pattern', type=str)


class Reimager(object):
    """
    A class that can run jobs to reimage devices.

    @var _afe: a frontend.AFE instance used to talk to autotest.
    @var _tko: a frontend.TKO instance used to query the autotest results db.
    @var _cf_getter: a ControlFileGetter used to get the AU control file.
    """


    def __init__(self, autotest_dir, afe=None, tko=None, pool=None):
        """
        Constructor

        @param autotest_dir: the place to find autotests.
        @param afe: an instance of AFE as defined in server/frontend.py.
        @param tko: an instance of TKO as defined in server/frontend.py.
        @param pool: Specify the pool of machines to use for scheduling
                purposes.
        """
        self._afe = afe or frontend_wrappers.RetryingAFE(timeout_min=30,
                                                         delay_sec=10,
                                                         debug=False)
        self._tko = tko or frontend_wrappers.RetryingTKO(timeout_min=30,
                                                         delay_sec=10,
                                                         debug=False)
        self._pool = pool
        self._cf_getter = control_file_getter.FileSystemGetter(
            [os.path.join(autotest_dir, 'server/site_tests')])


    def skip(self, g):
        return 'SKIP_IMAGE' in g and g['SKIP_IMAGE']


    def attempt(self, build, board, record, num=None, pool=None):
        """
        Synchronously attempt to reimage some machines.

        Fire off attempts to reimage |num| machines of type |board|, using an
        image at |url| called |build|.  Wait for completion, polling every
        10s, and log results with |record| upon completion.

        @param build: the build to install e.g.
                      x86-alex-release/R18-1655.0.0-a1-b1584.
        @param board: which kind of devices to reimage.
        @param record: callable that records job status.
                 prototype:
                   record(status, subdir, name, reason)
        @param num: how many devices to reimage.
        @param pool: Specify the pool of machines to use for scheduling
                purposes.
        @return True if all reimaging jobs succeed, false otherwise.
        """
        if not num:
            num = CONFIG.get_config_value('CROS', 'sharding_factor', type=int)
        if pool:
          self._pool = pool
        logging.debug("scheduling reimaging across %d machines", num)
        wrapper_job_name = 'try new image'
        record('START', None, wrapper_job_name)
        self._ensure_version_label(VERSION_PREFIX + build)
        canary = self._schedule_reimage_job(build, num, board)
        logging.debug('Created re-imaging job: %d', canary.id)
        while len(self._afe.get_jobs(id=canary.id, not_yet_run=True)) > 0:
            time.sleep(10)
        logging.debug('Re-imaging job running.')
        while len(self._afe.get_jobs(id=canary.id, finished=True)) == 0:
            time.sleep(10)
        logging.debug('Re-imaging job finished.')
        canary.result = self._afe.poll_job_results(self._tko, canary, 0)

        if canary.result is True:
            self._report_results(canary, record)
            record('END GOOD', None, wrapper_job_name)
            return True

        if canary.result is None:
            record('FAIL', None, canary.name, 're-imaging tasks did not run')
        else:  # canary.result is False
            self._report_results(canary, record)

        record('END FAIL', None, wrapper_job_name)
        return False


    def _ensure_version_label(self, name):
        """
        Ensure that a label called |name| exists in the autotest DB.

        @param name: the label to check for/create.
        """
        labels = self._afe.get_labels(name=name)
        if len(labels) == 0:
            self._afe.create_label(name=name)


    def _schedule_reimage_job(self, build, num_machines, board):
        """
        Schedules the reimaging of |num_machines| |board| devices with |image|.

        Sends an RPC to the autotest frontend to enqueue reimaging jobs on
        |num_machines| devices of type |board|

        @param build: the build to install (must be unique).
        @param num_machines: how many devices to reimage.
        @param board: which kind of devices to reimage.
        @return a frontend.Job object for the reimaging job we scheduled.
        """
        control_file = inject_vars(
            {'image_url': _image_url_pattern() % build, 'image_name': build},
            self._cf_getter.get_control_file_contents_by_name('autoupdate'))
        job_deps = []
        if self._pool:
            meta_host = 'pool:%s' % self._pool
            board_label = 'board:%s' % board
            job_deps.append(board_label)
        else:
            # No pool specified use board.
            meta_host = 'board:%s' % board

        return self._afe.create_job(control_file=control_file,
                                    name=build + '-try',
                                    control_type='Server',
                                    meta_hosts=[meta_host] * num_machines,
                                    dependencies=job_deps)


    def _report_results(self, job, record):
        """
        Record results from a completed frontend.Job object.

        @param job: a completed frontend.Job object populated by
               frontend.AFE.poll_job_results.
        @param record: callable that records job status.
               prototype:
                 record(status, subdir, name, reason)
        """
        if job.result == True:
            record('GOOD', None, job.name)
            return

        for platform in job.results_platform_map:
            for status in job.results_platform_map[platform]:
                if status == 'Total':
                    continue
                for host in job.results_platform_map[platform][status]:
                    if host not in job.test_status:
                        record('ERROR', None, host, 'Job failed to run.')
                    elif status == 'Failed':
                        for test_status in job.test_status[host].fail:
                            record('FAIL', None, host, test_status.reason)
                    elif status == 'Aborted':
                        for test_status in job.test_status[host].fail:
                            record('ABORT', None, host, test_status.reason)
                    elif status == 'Completed':
                        record('GOOD', None, host)


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
    def create_ds_getter(build):
        """
        @param build: the build on which we're running this suite.
        @return a FileSystemGetter instance that looks under |autotest_dir|.
        """
        return control_file_getter.DevServerGetter(
            build, dev_server.DevServer.create())


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
    def create_from_name(name, build, cf_getter=None,
                         afe=None, tko=None, pool=None):
        """
        Create a Suite using a predicate based on the SUITE control file var.

        Makes a predicate based on |name| and uses it to instantiate a Suite
        that looks for tests in |autotest_dir| and will schedule them using
        |afe|.  Pulls control files from the default dev server.
        Results will be pulled from |tko| upon completion.

        @param name: a value of the SUITE control file variable to search for.
        @param build: the build on which we're running this suite.
        @param cf_getter: a control_file_getter.ControlFileGetter.
                          If None, default to using a DevServerGetter.
        @param afe: an instance of AFE as defined in server/frontend.py.
        @param tko: an instance of TKO as defined in server/frontend.py.
        @param pool: Specify the pool of machines to use for scheduling
                     purposes.
        @return a Suite instance.
        """
        if cf_getter is None:
            cf_getter = Suite.create_ds_getter(build)
        return Suite(lambda t: hasattr(t, 'suite') and t.suite == name,
                     name, build, cf_getter, afe, tko, pool)



    def __init__(self, predicate, tag, build, cf_getter, afe=None, tko=None,
                 pool=None):
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
        """
        self._predicate = predicate
        self._tag = tag
        self._build = build
        self._cf_getter = cf_getter
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
        @return frontend.Job object for the job just scheduled.
        """
        job_deps = []
        if self._pool:
            meta_hosts = 'pool:%s' % self._pool
            cros_label = VERSION_PREFIX + self._build
            job_deps.append(cros_label)
        else:
            # No pool specified use any machines with the following label.
            meta_hosts = VERSION_PREFIX + self._build

        return self._afe.create_job(
            control_file=test.text,
            name='/'.join([self._build, self._tag, test.name]),
            control_type=test.test_type.capitalize(),
            meta_hosts=[meta_hosts],
            dependencies=job_deps)


    def run_and_wait(self, record, add_experimental=True):
        """
        Synchronously run tests in |self.tests|.

        Schedules tests against a device running image |self._build|, and
        then polls for status, using |record| to print status when each
        completes.

        Tests returned by self.stable_tests() will always be run, while tests
        in self.unstable_tests() will only be run if |add_experimental| is true.

        @param record: callable that records job status.
                 prototype:
                   record(status, subdir, name, reason)
        @param add_experimental: schedule experimental tests as well, or not.
        """
        try:
            record('INFO', None, 'Start %s' % self._tag)
            self.schedule(add_experimental)
            try:
                for result in self.wait_for_results():
                    # |result| will be a tuple of a maximum of 4 entries and a
                    # minimum of 3. We use the first 3 for START and END
                    # entries so we separate those variables out for legible
                    # variable names, nothing more.
                    status = result[0]
                    test_name = result[2]
                    record('START', None, test_name)
                    record(*result)
                    record('END %s' % status, None, test_name)
            except Exception as e:
                logging.error(e)
                record('FAIL', None, self._tag,
                       'Exception waiting for results')
        except Exception as e:
            logging.error(e)
            record('FAIL', None, self._tag,
                   'Exception while scheduling suite')


    def schedule(self, add_experimental=True):
        """
        Schedule jobs using |self._afe|.

        frontend.Job objects representing each scheduled job will be put in
        |self._jobs|.

        @param add_experimental: schedule experimental tests as well, or not.
        """
        for test in self.stable_tests():
            logging.debug('Scheduling %s', test.name)
            self._jobs.append(self._create_job(test))

        if add_experimental:
            # TODO(cmasone): ensure I can log results from these differently.
            for test in self.unstable_tests():
                logging.debug('Scheduling %s', test.name)
                self._jobs.append(self._create_job(test))


    def _status_is_relevant(self, status):
        """
        Indicates whether the status of a given test is meaningful or not.

        @param status: frontend.TestStatus object to look at.
        @return True if this is a test result worth looking at further.
        """
        return not (status.test_name.startswith('SERVER_JOB') or
                    status.test_name.startswith('CLIENT_JOB'))


    def _collate_aborted(self, current_value, entry):
        """
        reduce() over a list of HostQueueEntries for a job; True if any aborted.

        Functor that can be reduced()ed over a list of
        HostQueueEntries for a job.  If any were aborted
        (|entry.aborted| exists and is True), then the reduce() will
        return True.

        Ex:
            entries = self._afe.run('get_host_queue_entries', job=job.id)
            reduce(self._collate_aborted, entries, False)

        @param current_value: the current accumulator (a boolean).
        @param entry: the current entry under consideration.
        @return the value of |entry.aborted| if it exists, False if not.
        """
        return current_value or ('aborted' in entry and entry['aborted'])


    def wait_for_results(self):
        """
        Wait for results of all tests in all jobs in |self._jobs|.

        Currently polls for results every 5s.  When all results are available,
        @return a list of tuples, one per test: (status, subdir, name, reason)
        """
        while self._jobs:
            for job in list(self._jobs):
                if not self._afe.get_jobs(id=job.id, finished=True):
                    continue

                self._jobs.remove(job)

                entries = self._afe.run('get_host_queue_entries', job=job.id)
                if reduce(self._collate_aborted, entries, False):
                    yield('ABORT', None, job.name)
                else:
                    statuses = self._tko.get_status_counts(job=job.id)
                    for s in filter(self._status_is_relevant, statuses):
                        yield(s.status, None, s.test_name, s.reason)
            time.sleep(5)


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
                file text added in |text| attribute.
        """
        tests = {}
        files = cf_getter.get_control_file_list()
        for file in files:
            text = cf_getter.get_control_file_contents(file)
            try:
                found_test = control_data.parse_control_string(text,
                                                            raise_warnings=True)
                if not add_experimental and found_test.experimental:
                    continue

                found_test.text = text
                tests[file] = found_test
            except control_data.ControlVariableException, e:
                logging.warn("Skipping %s\n%s", file, e)
            except Exception, e:
                logging.error("Bad %s\n%s", file, e)

        return [test for test in tests.itervalues() if predicate(test)]
