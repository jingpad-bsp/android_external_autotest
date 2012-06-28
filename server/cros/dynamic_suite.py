# Copyright (c) 2012 The Chromium OS Authors. All rights reserved.
# Use of this source code is governed by a BSD-style license that can be
# found in the LICENSE file.

import common
import compiler, datetime, hashlib, logging, os, random, re, time, traceback
from autotest_lib.client.common_lib import base_job, control_data, global_config
from autotest_lib.client.common_lib import error, utils
from autotest_lib.client.common_lib.cros import dev_server
from autotest_lib.server.cros import control_file_getter, frontend_wrappers
from autotest_lib.server.cros import job_status
from autotest_lib.server.cros.job_status import Status
from autotest_lib.server import frontend
from autotest_lib.frontend.afe.json_rpc import proxy

"""CrOS dynamic test suite generation and execution module.

This module implements runtime-generated test suites for CrOS.
Design doc: http://goto.google.com/suitesv2

Individual tests can declare themselves as a part of one or more
suites, and the code here enables control files to be written
that can refer to these "dynamic suites" by name.  We also provide
support for reimaging devices with a given build and running a
dynamic suite across all reimaged devices.

The public API for defining a suite includes one method: reimage_and_run().
A suite control file can be written by importing this module and making
an appropriate call to this single method.  In normal usage, this control
file will be run in a 'hostless' server-side autotest job, scheduling
sub-jobs to do the needed reimaging and test running.

Example control file:

import common
from autotest_lib.server.cros import dynamic_suite

dynamic_suite.reimage_and_run(
    build=build, board=board, name='bvt', job=job, pool=pool,
    check_hosts=check_hosts, add_experimental=True, num=4,
    skip_reimage=dynamic_suite.skip_reimage(globals()))

This will -- at runtime -- find all control files that contain "bvt"
in their "SUITE=" clause, schedule jobs to reimage 4 devices in the
specified pool of the specified board with the specified build and,
upon completion of those jobs, schedule and wait for jobs that run all
the tests it discovered across those 4 machines.

Suites can be run by using the atest command-line tool:
  atest suite create -b <board> -i <build/name> <suite>
e.g.
  atest suite create -b x86-mario -i x86-mario/R20-2203.0.0 bvt

-------------------------------------------------------------------------
Implementation details

In addition to the create_suite_job() RPC defined in the autotest frontend,
there are two main classes defined here: Suite and Reimager.

A Suite instance represents a single test suite, defined by some predicate
run over all known control files.  The simplest example is creating a Suite
by 'name'.

The Reimager class provides support for reimaging a heterogenous set
of devices with an appropriate build, in preparation for a test run.
One could use a single Reimager, followed by the instantiation and use
of multiple Suite objects.

create_suite_job() takes the parameters needed to define a suite run (board,
build to test, machine pool, and which suite to run), ensures important
preconditions are met, finds the appropraite suite control file, and then
schedules the hostless job that will do the rest of the work.

reimage_and_run() works by creating a Reimager, using it to perform the
requested installs, and then instantiating a Suite and running it on the
machines that were just reimaged.  We'll go through this process in stages.

- create_suite_job()
The primary role of create_suite_job() is to ensure that the required
artifacts for the build to be tested are staged on the dev server.  This
includes payloads required to autoupdate machines to the desired build, as
well as the autotest control files appropriate for that build.  Then, the
RPC pulls the control file for the suite to be run from the dev server and
uses it to create the suite job with the autotest frontend.

     +----------------+
     | Google Storage |                                Client
     +----------------+                                   |
               | ^                                        | create_suite_job()
 payloads/     | |                                        |
 control files | | request                                |
               V |                                        V
       +-------------+   download request    +--------------------------+
       |             |<----------------------|                          |
       | Dev Server  |                       | Autotest Frontend (AFE)  |
       |             |---------------------->|                          |
       +-------------+  suite control file   +--------------------------+
                                                          |
                                                          V
                                                      Suite Job (hostless)

- The Reimaging process
In short, the Reimager schedules and waits for a number of autoupdate 'test'
jobs that perform image installation and make sure the device comes back up.
It labels the machines that it reimages with the newly-installed CrOS version,
so that later steps in the can refer to the machines by version and board,
instead of having to keep track of hostnames or some such.

The number of machines to use is called the 'sharding_factor', and the default
is defined in the [CROS] section of global_config.ini.  This can be overridden
by passing a 'num=N' parameter to reimage_and_run() as shown in the example
above.

Step by step:
1) Schedule autoupdate 'tests' across N devices of the appropriate board.
  - Technically, one job that has N tests across N hosts.
  - This 'test' is in server/site_tests/autoupdate/
  - The control file is modified at runtime to inject the name of the build
    to install, and the URL to get said build from.
  - This is the _TOT_ version of the autoupdate test; it must be able to run
    successfully on all currently supported branches at all times.
2) Wait for this job to get kicked off and run to completion.
3) Label successfully reimaged devices with a 'cros-version' label
  - This is actually done by the autoupdate 'test' control file.
4) Add a host attribute ('job_repo_url') to each reimaged host indicating
   the URL where packages should be downloaded for subsequent tests
  - This is actually done by the autoupdate 'test' control file
  - This information is consumed in server/site_autotest.py
  - job_repo_url points to some location on the dev server, where build
    artifacts are staged -- including autotest packages.
5) Return success or failure.

          +------------+                       +--------------------------+
          |            |                       |                          |
          | Dev Server |                       | Autotest Frontend (AFE)  |
          |            |                       |       [Suite Job]        |
          +------------+                       +--------------------------+
           | payloads |                                |   |     |
           V          V             autoupdate test    |   |     |
    +--------+       +--------+ <-----+----------------+   |     |
    | Host 1 |<------| Host 2 |-------+                    |     |
    +--------+       +--------+              label         |     |
     VersLabel        VersLabel    <-----------------------+     |
     job_repo_url     job_repo_url <-----------------------------+
                                          host-attribute

To sum up, after re-imaging, we have the following assumptions:
- |num| devices of type |board| have |build| installed.
- These devices are labeled appropriately
- They have a host attribute called 'job_repo_url' dictating where autotest
  packages can be downloaded for test runs.


- Running Suites
A Suite instance uses the labels created by the Reimager to schedule test jobs
across all the hosts that were just reimaged.  It then waits for all these jobs.

Step by step:
1) At instantiation time, find all appropriate control files for this suite
   that were included in the build to be tested.  To do this, we consult the
   Dev Server, where all these control files are staged.

          +------------+    control files?     +--------------------------+
          |            |<----------------------|                          |
          | Dev Server |                       | Autotest Frontend (AFE)  |
          |            |---------------------->|       [Suite Job]        |
          +------------+    control files!     +--------------------------+

2) Now that the Suite instance exists, it schedules jobs for every control
   file it deemed appropriate, to be run on the hosts that were labeled
   by the Reimager.  We stuff keyvals into these jobs, indicating what
   build they were testing and which suite they were for.

   +--------------------------+ Job for VersLabel       +--------+
   |                          |------------------------>| Host 1 | VersLabel
   | Autotest Frontend (AFE) |            +--------+   +--------+
   |       [Suite Job]        |----------->| Host 2 |
   +--------------------------+ Job for    +--------+
       |                ^       VersLabel        VersLabel
       |                |
       +----------------+
        One job per test
        {'build': build/name,
         'suite': suite_name}

3) Now that all jobs are scheduled, they'll be doled out as labeled hosts
   finish their assigned work and become available again.
4) As we clean up each job, we check to see if any crashes occurred.  If they
   did, we look at the 'build' keyval in the job to see which build's debug
   symbols we'll need to symbolicate the crash dump we just found.
5) Using this info, we tell the Dev Server to stage the required debug symbols.
   Once that's done, we ask the dev server to use those symbols to symbolicate
   the crash dump in question.

     +----------------+
     | Google Storage |
     +----------------+
          |     ^
 symbols! |     | symbols?
          V     |
      +------------+  stage symbols for build  +--------------------------+
      |            |<--------------------------|                          |
      |            |                           |                          |
      | Dev Server |   dump to symbolicate     | Autotest Frontend (AFE)  |
      |            |<--------------------------|       [Suite Job]        |
      |            |-------------------------->|                          |
      +------------+    symbolicated dump      +--------------------------+

6) As jobs finish, we record their success or failure in the status of the suite
   job.  We also record a 'job keyval' in the suite job for each test, noting
   the job ID and job owner.  This can be used to refer to test logs later.
7) Once all jobs are complete, status is recorded for the suite job, and the
   job_repo_url host attribute is removed from all hosts used by the suite.

"""


# Job keyvals for finding debug symbols when processing crash dumps.
JOB_BUILD_KEY = 'build'
JOB_SUITE_KEY = 'suite'

# Job attribute and label names
JOB_REPO_URL = 'job_repo_url'
VERSION_PREFIX = 'cros-version:'
EXPERIMENTAL_PREFIX = 'experimental_'
REIMAGE_JOB_NAME = 'try_new_image'

# Timings
ARTIFACT_FINISHED_TIME = 'artifact_finished_time'
DOWNLOAD_STARTED_TIME = 'download_started_time'
PAYLOAD_FINISHED_TIME = 'payload_finished_time'

CONFIG = global_config.global_config


# Relevant CrosDynamicSuiteExceptions are defined in client/common_lib/error.py.


def reimage_and_run(**dargs):
    """
    Backward-compatible API for dynamic_suite.

    Will re-image a number of devices (of the specified board) with the
    provided build, and then run the indicated test suite on them.
    Guaranteed to be compatible with any build from stable to dev.

    Currently required args:
    @param build: the build to install e.g.
                  x86-alex-release/R18-1655.0.0-a1-b1584.
    @param board: which kind of devices to reimage.
    @param name: a value of the SUITE control file variable to search for.
    @param job: an instance of client.common_lib.base_job representing the
                currently running suite job.

    Currently supported optional args:
    @param pool: specify the pool of machines to use for scheduling purposes.
                 Default: None
    @param num: how many devices to reimage.
                Default in global_config
    @param check_hosts: require appropriate hosts to be available now.
    @param skip_reimage: skip reimaging, used for testing purposes.
                         Default: False
    @param add_experimental: schedule experimental tests as well, or not.
                             Default: True
    @raises AsynchronousBuildFailure: if there was an issue finishing staging
                                      from the devserver.
    """
    (build, board, name, job, pool, num, check_hosts, skip_reimage,
     add_experimental) = _vet_reimage_and_run_args(**dargs)
    board = 'board:%s' % board
    if pool:
        pool = 'pool:%s' % pool
    reimager = Reimager(job.autodir, results_dir=job.resultdir)

    if skip_reimage or reimager.attempt(build, board, pool, job.record_entry,
                                        check_hosts, num=num):
        # Ensure that the image's artifacts have completed downloading.
        try:
            ds = dev_server.DevServer.create()
            ds.finish_download(build)
        except dev_server.DevServerException as e:
            raise error.AsynchronousBuildFailure(e)

        timestamp = datetime.datetime.now().strftime(job_status.TIME_FMT)
        utils.write_keyval(job.resultdir,
                           {ARTIFACT_FINISHED_TIME: timestamp})

        suite = Suite.create_from_name(name, build, pool=pool,
                                       results_dir=job.resultdir)
        suite.run_and_wait(job.record_entry, add_experimental=add_experimental)

    reimager.clear_reimaged_host_state(build)


def _vet_reimage_and_run_args(build=None, board=None, name=None, job=None,
                              pool=None, num=None, check_hosts=True,
                              skip_reimage=False, add_experimental=True,
                              **dargs):
    """
    Vets arguments for reimage_and_run().

    Currently required args:
    @param build: the build to install e.g.
                  x86-alex-release/R18-1655.0.0-a1-b1584.
    @param board: which kind of devices to reimage.
    @param name: a value of the SUITE control file variable to search for.
    @param job: an instance of client.common_lib.base_job representing the
                currently running suite job.

    Currently supported optional args:
    @param pool: specify the pool of machines to use for scheduling purposes.
                 Default: None
    @param num: how many devices to reimage.
                Default in global_config
    @param check_hosts: require appropriate hosts to be available now.
    @param skip_reimage: skip reimaging, used for testing purposes.
                         Default: False
    @param add_experimental: schedule experimental tests as well, or not.
                             Default: True
    @return a tuple of args set to provided (or default) values.
    """
    required_keywords = {'build': str,
                         'board': str,
                         'name': str,
                         'job': base_job.base_job}
    for key, expected in required_keywords.iteritems():
        value = locals().get(key)
        if not value or not isinstance(value, expected):
            raise error.SuiteArgumentException(
                "reimage_and_run() needs %s=<%r>" % (key, expected))
    return (build, board, name, job, pool, num, check_hosts, skip_reimage,
            add_experimental)


def inject_vars(vars, control_file_in):
    """
    Inject the contents of |vars| into |control_file_in|.

    @param vars: a dict to shoehorn into the provided control file string.
    @param control_file_in: the contents of a control file to munge.
    @return the modified control file string.
    """
    control_file = ''
    for key, value in vars.iteritems():
        # None gets injected as 'None' without this check; same for digits.
        if isinstance(value, str):
            control_file += "%s='%s'\n" % (key, value)
        else:
            control_file += "%s=%r\n" % (key, value)
    return control_file + control_file_in


def _image_url_pattern():
    return CONFIG.get_config_value('CROS', 'image_url_pattern', type=str)


def _package_url_pattern():
    return CONFIG.get_config_value('CROS', 'package_url_pattern', type=str)


def skip_reimage(g):
    return g.get('SKIP_IMAGE')


class Reimager(object):
    """
    A class that can run jobs to reimage devices.

    @var _afe: a frontend.AFE instance used to talk to autotest.
    @var _tko: a frontend.TKO instance used to query the autotest results db.
    @var _cf_getter: a ControlFileGetter used to get the AU control file.
    """


    def __init__(self, autotest_dir, afe=None, tko=None, results_dir=None):
        """
        Constructor

        @param autotest_dir: the place to find autotests.
        @param afe: an instance of AFE as defined in server/frontend.py.
        @param tko: an instance of TKO as defined in server/frontend.py.
        @param results_dir: The directory where the job can write results to.
                            This must be set if you want job_id of sub-jobs
                            list in the job keyvals.
        """
        self._afe = afe or frontend_wrappers.RetryingAFE(timeout_min=30,
                                                         delay_sec=10,
                                                         debug=False)
        self._tko = tko or frontend_wrappers.RetryingTKO(timeout_min=30,
                                                         delay_sec=10,
                                                         debug=False)
        self._results_dir = results_dir
        self._reimaged_hosts = {}
        self._cf_getter = control_file_getter.FileSystemGetter(
            [os.path.join(autotest_dir, 'server/site_tests')])


    def skip(self, g):
        """Deprecated in favor of dynamic_suite.skip_reimage()."""
        return 'SKIP_IMAGE' in g and g['SKIP_IMAGE']


    def attempt(self, build, board, pool, record, check_hosts, num=None):
        """
        Synchronously attempt to reimage some machines.

        Fire off attempts to reimage |num| machines of type |board|, using an
        image at |url| called |build|.  Wait for completion, polling every
        10s, and log results with |record| upon completion.

        @param build: the build to install e.g.
                      x86-alex-release/R18-1655.0.0-a1-b1584.
        @param board: which kind of devices to reimage.
        @param pool: Specify the pool of machines to use for scheduling
                purposes.
        @param record: callable that records job status.
               prototype:
                 record(base_job.status_log_entry)
        @param check_hosts: require appropriate hosts to be available now.
        @param num: how many devices to reimage.
        @return True if all reimaging jobs succeed, false otherwise.
        """
        if not num:
            num = CONFIG.get_config_value('CROS', 'sharding_factor', type=int)
        logging.debug("scheduling reimaging across %d machines", num)
        begin_time_str = datetime.datetime.now().strftime(job_status.TIME_FMT)
        try:
            self._ensure_version_label(VERSION_PREFIX + build)

            if check_hosts:
                # TODO make DEPENDENCIES-aware
                self._ensure_enough_hosts(board, pool, num)

            # Schedule job and record job metadata.
            # TODO make DEPENDENCIES-aware
            canary_job = self._schedule_reimage_job(build, board, pool, num)
            self._record_job_if_possible(REIMAGE_JOB_NAME, canary_job)
            logging.debug('Created re-imaging job: %d', canary_job.id)

            # Poll until reimaging is complete.
            self._wait_for_job_to_start(canary_job.id)
            self._wait_for_job_to_finish(canary_job.id)

            # Gather job results.
            canary_job.result = self._afe.poll_job_results(self._tko,
                                                           canary_job,
                                                           0)
        except error.InadequateHostsException as e:
            logging.warning(e)
            Status('WARN', REIMAGE_JOB_NAME, str(e),
                   begin_time_str=begin_time_str).record_all(record)
            return False
        except Exception as e:
            # catch Exception so we record the job as terminated no matter what.
            logging.error(e)
            Status('ERROR', REIMAGE_JOB_NAME, str(e),
                   begin_time_str=begin_time_str).record_all(record)
            return False

        self._remember_reimaged_hosts(build, canary_job)

        if canary_job.result is True:
            self._report_results(canary_job, record)
            return True

        if canary_job.result is None:
            Status('FAIL', canary_job.name,
                   'reimaging tasks did not run',
                   begin_time_str=begin_time_str).record_all(record)

        else:  # canary_job.result is False
            self._report_results(canary_job, record)

        return False


    def _ensure_enough_hosts(self, board, pool, num):
        """
        Determine if there are enough working hosts to run on.

        Raises exception if there are not enough hosts.

        @param board: which kind of devices to reimage.
        @param pool: the pool of machines to use for scheduling purposes.
        @param num: how many devices to reimage.
        @raises NoHostsException: if no working hosts.
        @raises InadequateHostsException: if too few working hosts.
        """
        labels = [l for l in [board, pool] if l is not None]
        available = self._count_usable_hosts(labels)
        if available == 0:
            raise error.NoHostsException('All hosts with %r are dead!' % labels)
        elif num > available:
            raise error.InadequateHostsException(
                'Too few hosts with %r' % labels)


    def _wait_for_job_to_start(self, job_id):
        """
        Wait for the job specified by |job_id| to start.

        @param job_id: the job ID to poll on.
        """
        while len(self._afe.get_jobs(id=job_id, not_yet_run=True)) > 0:
            time.sleep(10)
        logging.debug('Re-imaging job running.')


    def _wait_for_job_to_finish(self, job_id):
        """
        Wait for the job specified by |job_id| to finish.

        @param job_id: the job ID to poll on.
        """
        while len(self._afe.get_jobs(id=job_id, finished=True)) == 0:
            time.sleep(10)
        logging.debug('Re-imaging job finished.')


    def _remember_reimaged_hosts(self, build, canary_job):
        """
        Remember hosts that were reimaged with |build| as a part |canary_job|.

        @param build: the build that was installed e.g.
                      x86-alex-release/R18-1655.0.0-a1-b1584.
        @param canary_job: a completed frontend.Job object, possibly populated
                           by frontend.AFE.poll_job_results.
        """
        if not hasattr(canary_job, 'results_platform_map'):
            return
        if not self._reimaged_hosts.get('build'):
            self._reimaged_hosts[build] = []
        for platform in canary_job.results_platform_map:
            for host in canary_job.results_platform_map[platform]['Total']:
                self._reimaged_hosts[build].append(host)


    def clear_reimaged_host_state(self, build):
        """
        Clear per-host state created in the autotest DB for this job.

        After reimaging a host, we label it and set some host attributes on it
        that are then used by the suite scheduling code.  This call cleans
        that up.

        @param build: the build whose hosts we want to clean up e.g.
                      x86-alex-release/R18-1655.0.0-a1-b1584.
        """
        for host in self._reimaged_hosts.get('build', []):
            self._clear_build_state(host)


    def _clear_build_state(self, machine):
        """
        Clear all build-specific labels, attributes from the target.

        @param machine: the host to clear labels, attributes from.
        """
        self._afe.set_host_attribute(JOB_REPO_URL, None, hostname=machine)


    def _record_job_if_possible(self, test_name, job):
        """
        Record job id as keyval, if possible, so it can be referenced later.

        If |self._results_dir| is None, then this is a NOOP.

        @param test_name: the test to record id/owner for.
        @param job: the job object to pull info from.
        """
        if self._results_dir:
            job_id_owner = '%s-%s' % (job.id, job.owner)
            utils.write_keyval(
                self._results_dir,
                {hashlib.md5(test_name).hexdigest(): job_id_owner})


    def _count_usable_hosts(self, host_spec):
        """
        Given a set of host labels, count the live hosts that have them all.

        @param host_spec: list of labels specifying a set of hosts.
        @return the number of live hosts that satisfy |host_spec|.
        """
        count = 0
        for h in self._afe.get_hosts(multiple_labels=host_spec):
            if h.status not in ['Repair Failed', 'Repairing']:
                count += 1
        return count


    def _ensure_version_label(self, name):
        """
        Ensure that a label called |name| exists in the autotest DB.

        @param name: the label to check for/create.
        """
        try:
            self._afe.create_label(name=name)
        except proxy.ValidationError as ve:
            if ('name' in ve.problem_keys and
                'This value must be unique' in ve.problem_keys['name']):
                logging.debug('Version label %s already exists', name)
            else:
                raise ve


    def _schedule_reimage_job(self, build, board, pool, num_machines):
        """
        Schedules the reimaging of |num_machines| |board| devices with |image|.

        Sends an RPC to the autotest frontend to enqueue reimaging jobs on
        |num_machines| devices of type |board|

        @param build: the build to install (must be unique).
        @param board: which kind of devices to reimage.
        @param pool: the pool of machines to use for scheduling purposes.
        @param num_machines: how many devices to reimage.
        @return a frontend.Job object for the reimaging job we scheduled.
        """
        control_file = inject_vars(
            {'image_url': _image_url_pattern() % build, 'image_name': build},
            self._cf_getter.get_control_file_contents_by_name('autoupdate'))
        job_deps = []
        if pool:
            meta_host = pool
            board_label = board
            job_deps.append(board_label)
        else:
            # No pool specified use board.
            meta_host = board

        return self._afe.create_job(control_file=control_file,
                                    name=build + '-try',
                                    control_type='Server',
                                    priority='Low',
                                    meta_hosts=[meta_host] * num_machines,
                                    dependencies=job_deps)


    def _report_results(self, job, record):
        """
        Record results from a completed frontend.Job object.

        @param job: a completed frontend.Job object populated by
               frontend.AFE.poll_job_results.
        @param record: callable that records job status.
               prototype:
                 record(base_job.status_log_entry)
        """
        status_map = {'Failed': 'FAIL', 'Aborted': 'ABORT', 'Completed': 'GOOD'}
        for platform in job.results_platform_map:
            for status in job.results_platform_map[platform]:
                if status == 'Total':
                    continue
                for host in job.results_platform_map[platform][status]:
                    if host not in job.test_status:
                        Status('ERROR', host,
                               'Job failed to run.').record_all(record)

                    elif status in status_map:
                        for test_status in (job.test_status[host].fail +
                                            job.test_status[host].good):
                            result = Status(status_map[status],
                                            '%s-%s' % (REIMAGE_JOB_NAME, host),
                                            test_status.reason,
                                            test_status.test_started_time,
                                            test_status.test_finished_time)
                            result.record_all(record)
                    else:
                        logging.error('Unknown status ' + status)


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
    def parse_tag(tag):
        """Splits a string on ',' optionally surrounded by whitespace."""
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
    def list_all_suites(build, cf_getter=None):
        """
        Parses all ControlData objects with a SUITE tag and extracts all
        defined suite names.

        @param cf_getter: control_file_getter.ControlFileGetter. Defaults to
                          using DevServerGetter.

        @return list of suites
        """
        if cf_getter is None:
            cf_getter = Suite.create_ds_getter(build)

        suites = set()
        predicate = lambda t: hasattr(t, 'suite')
        for test in Suite.find_and_parse_tests(cf_getter, predicate,
                                               add_experimental=True):
            suites.update(Suite.parse_tag(test.suite))
        return list(suites)


    @staticmethod
    def create_from_name(name, build, cf_getter=None, afe=None, tko=None,
                         pool=None, results_dir=None):
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
        @param results_dir: The directory where the job can write results to.
                            This must be set if you want job_id of sub-jobs
                            list in the job keyvals.
        @return a Suite instance.
        """
        if cf_getter is None:
            cf_getter = Suite.create_ds_getter(build)
        return Suite(Suite.name_in_tag_predicate(name),
                     name, build, cf_getter, afe, tko, pool, results_dir)


    def __init__(self, predicate, tag, build, cf_getter, afe=None, tko=None,
                 pool=None, results_dir=None):
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
        job_deps = []  # TODO(cmasone): init from test.dependencies.
        if self._pool:
            meta_hosts = self._pool
            cros_label = VERSION_PREFIX + self._build
            job_deps.append(cros_label)
        else:
            # No pool specified use any machines with the following label.
            meta_hosts = VERSION_PREFIX + self._build
        test_obj = self._afe.create_job(
            control_file=test.text,
            name='/'.join([self._build, self._tag, test.name]),
            control_type=test.test_type.capitalize(),
            meta_hosts=[meta_hosts],
            dependencies=job_deps,
            keyvals={JOB_BUILD_KEY: self._build, JOB_SUITE_KEY: self._tag})

        setattr(test_obj, 'test_name', test.name)

        return test_obj


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
                   record(base_job.status_log_entry)
        @param add_experimental: schedule experimental tests as well, or not.
        """
        logging.debug('Discovered %d stable tests.', len(self.stable_tests()))
        logging.debug('Discovered %d unstable tests.',
                      len(self.unstable_tests()))
        try:
            Status('INFO', 'Start %s' % self._tag).record_result(record)
            self.schedule(add_experimental)
            try:
                for result in job_status.wait_for_results(self._afe,
                                                          self._tko,
                                                          self._jobs):
                    result.record_all(record)

            except Exception as e:
                logging.error(traceback.format_exc())
                Status('FAIL', self._tag,
                       'Exception waiting for results').record_result(record)
        except Exception as e:
            logging.error(traceback.format_exc())
            Status('FAIL', self._tag,
                   'Exception while scheduling suite').record_result(record)
        # Sanity check
        tests_at_end = self.find_and_parse_tests(self._cf_getter,
                                                 self._predicate,
                                                 add_experimental=True)
        if len(self.tests) != len(tests_at_end):
            msg = 'Dev Server enumerated %d tests at start, %d at end.' % (
                len(self.tests), len(tests_at_end))
            Status('FAIL', self._tag, msg).record_result(record)


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
            for test in self.unstable_tests():
                logging.debug('Scheduling experimental %s', test.name)
                test.name = EXPERIMENTAL_PREFIX + test.name
                self._jobs.append(self._create_job(test))
        if self._results_dir:
            self._record_scheduled_jobs()


    def _record_scheduled_jobs(self):
        """
        Record scheduled job ids as keyvals, so they can be referenced later.
        """
        for job in self._jobs:
            job_id_owner = '%s-%s' % (job.id, job.owner)
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
                file text added in |text| attribute.
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

        return [test for test in tests.itervalues() if predicate(test)]
