# Copyright (c) 2012 The Chromium OS Authors. All rights reserved.
# Use of this source code is governed by a BSD-style license that can be
# found in the LICENSE file.

import ast, compiler, datetime, hashlib, logging, os, random, re, time
import traceback

import common

from autotest_lib.client.common_lib import base_job, control_data, global_config
from autotest_lib.client.common_lib import error, utils
from autotest_lib.client.common_lib.cros import dev_server
from autotest_lib.server.cros.dynamic_suite import constants
from autotest_lib.server.cros.dynamic_suite import control_file_getter
from autotest_lib.server.cros.dynamic_suite import frontend_wrappers
from autotest_lib.server.cros.dynamic_suite import host_lock_manager, job_status
from autotest_lib.server.cros.dynamic_suite.job_status import Status
from autotest_lib.server.cros.dynamic_suite.reimager import FwReimager
from autotest_lib.server.cros.dynamic_suite.reimager import OsReimager
from autotest_lib.server.cros.dynamic_suite.suite import Suite
from autotest_lib.server import frontend


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
from autotest_lib.server.cros.dynamic_suite import dynamic_suite

dynamic_suite.reimage_and_run(
    build=build, board=board, name='bvt', job=job, pool=pool,
    check_hosts=check_hosts, add_experimental=True, num=num,
    skip_reimage=dynamic_suite.skip_reimage(globals()))

This will -- at runtime -- find all control files that contain "bvt" in their
"SUITE=" clause, schedule jobs to reimage |num| or less devices in the
specified pool of the specified board with the specified build and, upon
completion of those jobs, schedule and wait for jobs that run all the tests it
discovered across those |num| or less machines.

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

Note that we have more than one Dev server in our test lab architecture.
We currently load balance per-build being tested, so one and only one dev
server is used by any given run through the reimaging/testing flow.

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
instead of having to keep track of hostnames or some such.  Furthermore, these
machines are 'Locked' in the AFE as soon as they have started to go through
reimaging.  They will be unlocked as soon as the suite's actual test jobs
have been scheduled against them.  This is to avoid races between different
suites trying to grab machines at the same time.

The number of machines to use is called the 'sharding_factor', and the default
is defined in the [CROS] section of global_config.ini.  This can be overridden
by passing a 'num=N' parameter to create_suite_job(), which is piped through
to reimage_and_run() just like the 'build' and 'board' parameters are.

A test control file can specify a list of DEPENDENCIES, which are really just
the set of labels a host needs to have in order for that test to be scheduled
on it.  In the case of a dynamic_suite, many tests in the suite may have
DEPENDENCIES specified.  They may overlap, they may not.  This complicates
reimaging, as we need to try to cover the DEPENDENCIES of all tests in the
suite while still staying within the sharding_factor.

A lengthier discussion is available at:
http://goto.google.com/dynamic-suites-deps

For now, we use a naive algorithm to find a set of machines that can
satisfy all the test DEPENDENCIES in a given suite.
Per-test-per-suite DEPENDENCIES information is generated at build
time, and then fetched and consumed during suite preparation.  If info
exists for the suite being run, the infrastructure will look for a
host that matches each unique DEPENDENCY list.  If it can find such a
set that is <= the suite sharding factor, the infrastructure will
schedule those machines for reimaging.  If not, the suite will fail.
If a suite has no DEPENDENCIES info, we just do the standard meta_host-based
scheduling.


Step by step:
0) Fetch DEPENDENCIES info for the suite to be run.
1) Process the DEPENDENCIES with whatever board and device 'pool' are
   specified to create a list of unique dependency lists.
2) Determine what hosts we need to reimage.
   2a) If we have no DEPENDENCIES, set up a meta_host that specifies N hosts of
       the right board in the right pool and move on.
   2b) If we do, query the AFE to find at least one live host that matches
       each dependency list.  If some list has no matching hosts, bail.
       If we have more lists than our sharding_factor, bail.
3) Schedule autoupdate 'tests' across chosen devices.
  - Technically, one job that has N tests across N hosts.
  - This 'test' is in server/site_tests/autoupdate/control
  - The control file is modified at runtime to inject the name of the build
    to install, and the URL to get said build from.
  - This is the _TOT_ version of the autoupdate test; it must be able to run
    successfully on all currently supported branches at all times.
4) Wait for this job to get kicked off.
5) As each host is chosen by the scheduler and begins reimaging, lock it.
6) Wait for all reimaging to run to completion.
7) Label successfully reimaged devices with a 'cros-version' label
  - This is actually done by the autoupdate 'test' control file.
8) Add a host attribute ('job_repo_url') to each reimaged host indicating
   the URL where packages should be downloaded for subsequent tests
  - This is actually done by the autoupdate 'test' control file
  - This information is consumed in server/site_autotest.py
  - job_repo_url points to some location on the dev server, where build
    artifacts are staged -- including autotest packages.
9) Return success if at least one device successfully reimaged, or failure
   otherwise.

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
- At most |num| devices of type |board| have |build| installed.
- These devices are labeled appropriately
- They have a host attribute called 'job_repo_url' dictating where autotest
  packages can be downloaded for test runs.


- Running Suites
A Suite instance uses the labels created by the Reimager to schedule test jobs
across all the hosts that were just reimaged.  It then waits for all these jobs.
As an optimization, the Dev server stages the payloads necessary to run a suite
in the background _after_ it has completed all the things necessary for
reimaging.  Before running a suite, reimage_and_run() calls out to the Dev
server and blocks until it's completed staging all build artifacts needed to
run test suites.

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
   | Autotest Frontend (AFE)  |            +--------+   +--------+
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
5) Using this info, we tell a special Crash Server to stage the required debug
   symbols. Once that's done, we ask the Crash Server to use those symbols to
   symbolicate the crash dump in question.

     +----------------+
     | Google Storage |
     +----------------+
          |     ^
 symbols! |     | symbols?
          V     |
      +------------+  stage symbols for build  +--------------------------+
      |            |<--------------------------|                          |
      |   Crash    |                           |                          |
      |   Server   |   dump to symbolicate     | Autotest Frontend (AFE)  |
      |            |<--------------------------|       [Suite Job]        |
      |            |-------------------------->|                          |
      +------------+    symbolicated dump      +--------------------------+

6) As jobs finish, we record their success or failure in the status of the suite
   job.  We also record a 'job keyval' in the suite job for each test, noting
   the job ID and job owner.  This can be used to refer to test logs later.
7) Once all jobs are complete, status is recorded for the suite job, and the
   job_repo_url host attribute is removed from all hosts used by the suite.

"""


DEFAULT_TRY_JOB_TIMEOUT_MINS = global_config.global_config.get_config_value(
            'SCHEDULER', 'try_job_timeout_mins', type=int, default=4*60)

# Relevant CrosDynamicSuiteExceptions are defined in client/common_lib/error.py.

class SuiteSpec(object):
    """
    This class contains the info that defines a suite run.

    Currently required:
    @var build: the build to install e.g.
                  x86-alex-release/R18-1655.0.0-a1-b1584.
    @var board: which kind of devices to reimage.
    @var devserver: An instance of the devserver to use with this suite.
    @var name: a value of the SUITE control file variable to search for.
    @var job: an instance of client.common_lib.base_job representing the
                currently running suite job.

    Currently supported optional fields:
    @var pool: specify the pool of machines to use for scheduling purposes.
               Default: None
    @var num: the maximum number of devices to reimage.
              Default in global_config
    @var check_hosts: require appropriate hosts to be available now.
    @var skip_reimage: skip reimaging, used for testing purposes.
                       Default: False
    @var add_experimental: schedule experimental tests as well, or not.
                           Default: True
    @var dependencies: map of test names to dependency lists.
                       Initially {'': []}.
    """
    def __init__(self, build=None, board=None, name=None, job=None,
                 pool=None, num=None, check_hosts=True,
                 skip_reimage=False, add_experimental=True, file_bugs=False,
                 max_runtime_mins=24*60,
                 try_job_timeout_mins=DEFAULT_TRY_JOB_TIMEOUT_MINS, **dargs):
        """
        Vets arguments for reimage_and_run() and populates self with supplied
        values.

        Currently required args:
        @param build: the build to install e.g.
                      x86-alex-release/R18-1655.0.0-a1-b1584.
        @param board: which kind of devices to reimage.
        @param name: a value of the SUITE control file variable to search for.
        @param job: an instance of client.common_lib.base_job representing the
                    currently running suite job.

        Currently supported optional args:
        @param pool: specify the pool of machines to use for scheduling purposes
                     Default: None
        @param num: the maximum number of devices to reimage.
                    Default in global_config
        @param check_hosts: require appropriate hosts to be available now.
        @param skip_reimage: skip reimaging, used for testing purposes.
                             Default: False
        @param add_experimental: schedule experimental tests as well, or not.
                                 Default: True
        @param max_runtime_mins: Max runtime in mins for each of the sub-jobs
                                 this suite will run.
        @param try_job_timeout_mins: Max time in mins we allow a try job to run
                                     before timing out.
        @param **dargs: these arguments will be ignored.  This allows us to
                        deprecate and remove arguments in ToT while not
                        breaking branch builds.
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
        self.build = build
        self.board = 'board:%s' % board
        self.devserver = dev_server.ImageServer.resolve(self.build)
        self.name = name
        self.job = job
        if pool:
            self.pool = 'pool:%s' % pool
        else:
            self.pool = pool
        self.num = num
        self.check_hosts = check_hosts
        self.skip_reimage = skip_reimage
        self.add_experimental = add_experimental
        self.file_bugs = file_bugs
        self.dependencies = {'': []}
        self.max_runtime_mins = max_runtime_mins
        self.try_job_timeout_mins = try_job_timeout_mins


def skip_reimage(g):
    return g.get('SKIP_IMAGE')


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
    @param num: the maximum number of devices to reimage.
                Default in global_config
    @param check_hosts: require appropriate hosts to be available now.
    @param skip_reimage: skip reimaging, used for testing purposes.
                         Default: False
    @param add_experimental: schedule experimental tests as well, or not.
                             Default: True
    @param file_bugs: automatically file bugs on test failures.
                      Default: False
    @raises AsynchronousBuildFailure: if there was an issue finishing staging
                                      from the devserver.
    @raises MalformedDependenciesException: if the dependency_info file for
                                            the required build fails to parse.
    """
    suite_spec = SuiteSpec(**dargs)

    # Gather per-suite:per-test DEPENDENCIES info, if this build has it.
    all_dependencies = {}
    try:
        all_dependencies = ast.literal_eval(
            suite_spec.devserver.get_dependencies_file(suite_spec.build))
    except SyntaxError as e:
        if e.text:
            message = '%s has bad syntax in DEPENDENCIES info: %r' % (
                suite_spec.build, e)
        else:
            message = ('%s has a 0 byte DEPENDENCIES info file. Check the '
                       'build artifacts.') % suite_spec.build
        logging.error(message)
        raise error.MalformedDependenciesException(message)
    except (IndentationError, ValueError) as e:
        message = '%s has malformed DEPENDENCIES info: %r' % (suite_spec.build,
                                                              e)
        logging.error(message)
        raise error.MalformedDependenciesException(message)
    except dev_server.DevServerException:
        # Not all builds have dependency info at this time, which is OK.
        logging.info('Proceeding without DEPENDENCIES information.')
    suite_spec.dependencies = all_dependencies.get(suite_spec.name, {'': []})

    afe = frontend_wrappers.RetryingAFE(timeout_min=30, delay_sec=10,
                                        user=suite_spec.job.user, debug=False)
    tko = frontend_wrappers.RetryingTKO(timeout_min=30, delay_sec=10,
                                        user=suite_spec.job.user, debug=False)
    manager = host_lock_manager.HostLockManager(afe=afe)
    if dargs.get('firmware_reimage'):
        reimager_class = FwReimager
    else:
        reimager_class = OsReimager

    reimager = reimager_class(suite_spec.job.autodir, suite_spec.board, afe,
                              tko, results_dir=suite_spec.job.resultdir)

    _perform_reimage_and_run(suite_spec, afe, tko, reimager, manager)

    reimager.clear_reimaged_host_state(suite_spec.build)


def _perform_reimage_and_run(spec, afe, tko, reimager, manager):
    """
    Do the work of reimaging hosts and running tests.

    @param spec: a populated SuiteSpec object.
    @param afe: an instance of AFE as defined in server/frontend.py.
    @param tko: an instance of TKO as defined in server/frontend.py.
    @param reimager: the Reimager to use to reimage DUTs.
    @param manager: the HostLockManager to use to lock/unlock DUTs during
                    reimaging/test scheduling.
    """
    with host_lock_manager.HostsLockedBy(manager):
        tests_to_skip = []
        if spec.skip_reimage or reimager.attempt(spec.build, spec.pool,
                spec.devserver, spec.job.record_entry, spec.check_hosts,
                manager, tests_to_skip, spec.dependencies, num=spec.num,
                timeout_mins=spec.try_job_timeout_mins):
            # Ensure that the image's artifacts have completed downloading.
            try:
                spec.devserver.finish_download(spec.build)
            except dev_server.DevServerException as e:
                raise error.AsynchronousBuildFailure(e)

            timestamp = datetime.datetime.now().strftime(job_status.TIME_FMT)
            utils.write_keyval(
                spec.job.resultdir,
                {constants.ARTIFACT_FINISHED_TIME: timestamp})

            suite = Suite.create_from_name_and_blacklist(
                spec.name, tests_to_skip, spec.build, spec.devserver,
                afe=afe, tko=tko, pool=spec.pool,
                results_dir=spec.job.resultdir,
                max_runtime_mins=spec.max_runtime_mins,
                version_prefix=reimager.version_prefix)

            suite.run_and_wait(spec.job.record_entry, manager,
                               spec.add_experimental)
