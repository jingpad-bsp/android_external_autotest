# Copyright (c) 2012 The Chromium OS Authors. All rights reserved.
# Use of this source code is governed by a BSD-style license that can be
# found in the LICENSE file.


import datetime, hashlib, logging, os

import common

from autotest_lib.client.common_lib import error, utils
from autotest_lib.server.cros.dynamic_suite import constants
from autotest_lib.server.cros.dynamic_suite import control_file_getter
from autotest_lib.server.cros.dynamic_suite import frontend_wrappers
from autotest_lib.server.cros.dynamic_suite import host_spec
from autotest_lib.server.cros.dynamic_suite import job_status, tools
from autotest_lib.server.cros.dynamic_suite.host_spec import ExplicitHostGroup
from autotest_lib.server.cros.dynamic_suite.host_spec import HostSpec
from autotest_lib.server.cros.dynamic_suite.host_spec import MetaHostGroup
from autotest_lib.server.cros.dynamic_suite.job_status import Status
from autotest_lib.frontend.afe.json_rpc import proxy


DEFAULT_TRY_JOB_TIMEOUT_MINS = tools.try_job_timeout_mins()
_reimage_types = {}


def reimage_type(name):
    """
    A class decorator to register a reimager with a name of what type of
    reimaging it can do.
    @param name The name of the reimaging type to be registered.
    @return The true decorator that accepts the class to register as |name|.
    """
    def curry(klass):
        #pylint: disable-msg=C0111
        _reimage_types[name] = klass
        return klass
    return curry


def reimager_for(name):
    """
    Returns the reimager class associated with the given (string) name.

    @param name The name of the reimage type being requested.
    @return The subclass of Reimager that was requested.
    @raise KeyError if the name was not recognized as a reimage type.
    """
    return _reimage_types[name]


class Reimager(object):
    """
    A base class that can run jobs to reimage devices.

    Is subclassed to create reimagers for Chrome OS and firmware, which use
    different autotests to perform the action.

    @var _board: a string, name of the board type to reimage
    @var _afe: a frontend.AFE instance used to talk to autotest.
    @var _tko: a frontend.TKO instance used to query the autotest results db.
    @var _results_dir: The directory where the job can write results to.
                       This must be set if you want the 'name_job-id' tuple
                       of each per-device reimaging job listed in the
                       parent reimaging job's keyvals.
    @var _cf_getter: a ControlFileGetter used to get the appropriate autotest
                       control file.
    @var _version_prefix: a string, prefix for storing the build version in the
                       afe database. Set by the derived classes constructors.
    @var _control_file: a string, name of the file controlling the appropriate
                       reimaging autotest
    @var _url_pattern: a string, format used to generate url of the image on
                       the devserver
    """

    JOB_NAME = 'try_new_image'


    def __init__(self, autotest_dir, board_label, afe=None, tko=None,
                 results_dir=None):
        """
        Constructor

        @param autotest_dir: the place to find autotests.
        @param board_label: a string, label of the board type to reimage
        @param afe: an instance of AFE as defined in server/frontend.py.
        @param tko: an instance of TKO as defined in server/frontend.py.
        @param results_dir: The directory where the job can write results to.
                            This must be set if you want the 'name_job-id' tuple
                            of each per-device reimaging job listed in the
                            parent reimaging job's keyvals.
        @param canary_job: The reimage job that will get kicked off by the
                           |schedule| method.
        @param to_reimage: The list of machines that the reimage job will
                           attempt to reimage.
        """
        self._board_label = board_label
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
        self._version_prefix = None
        self._control_file = None
        self._url_pattern = None
        self._canary_job = None
        self._to_reimage = None


    def attempt(self, build, pool, devserver, record, check_hosts,
                tests_to_skip, dependencies={'':[]}, num=None,
                timeout_mins=DEFAULT_TRY_JOB_TIMEOUT_MINS):
        """
        Synchronously attempt to reimage some machines.

        See |schedule| and |wait| for more details.

        @param build: the build to install e.g.
                      x86-alex-release/R18-1655.0.0-a1-b1584.
        @param pool: Specify the pool of machines to use for scheduling
                purposes.
        @param devserver: an instance of a devserver to use to complete this
                  call.
        @param record: callable that records job status.
               prototype:
                 record(base_job.status_log_entry)
        @param check_hosts: require appropriate hosts to be available now.
        @param tests_to_skip: a list output parameter.  After execution, this
                              contains a list of control files not to run.
        @param dependencies: test-name-indexed dict of labels, e.g.
                             {'test1': ['label1', 'label2']}
                             Defaults to trivial set of dependencies, to cope
                             with builds that have no dependency information.

        @param num: the maximum number of devices to reimage.
        @param timeout_mins: Amount of time in mins to wait before timing out
                             this reimage attempt.
        @return True if all reimaging jobs succeed, false if they all fail or
                atleast one is aborted.
        """
        # This method still exists for unittesting convenience.
        if self.schedule(build, pool,
              devserver, record, check_hosts, tests_to_skip,
              dependencies, num):
            return self.wait(build, pool, record, check_hosts,
                      tests_to_skip, timeout_mins)

        return False


    def schedule(self, build, pool, devserver, record, check_hosts,
                 tests_to_skip, dependencies={'':[]}, num=None,
                 suite_job_id=None):
        """
        Asynchronously attempt to reimage some machines.

        Fire off attempts to reimage |num| machines of type |board|, using an
        image at |url| called |build|.

        Unfortunately, we can't rely on the scheduler to pick hosts for
        us when using dependencies.  The problem is that the scheduler
        treats all host queue entries as independent, and isn't capable
        of looking across a set of entries to make intelligent decisions
        about which hosts to use.  Consider a testbed that has only one
        'bluetooth'-labeled device, and a set of tests in which some
        require bluetooth and some could run on any machine.  If we
        schedule two reimaging jobs, one of which states that it should
        run on a bluetooth-having machine, the scheduler may choose to
        run the _other_ reimaging job (which has fewer constraints)
        on the DUT with the 'bluetooth' label -- thus starving the first
        reimaging job.  We can't schedule a single job with heterogeneous
        dependencies, either, as that is unsupported and devolves to the
        same problem: the scheduler is not designed to make decisions
        across multiple host queue entries.

        Given this, we'll grab lists of hosts on our own and make our
        own scheduling decisions.

        @param build: the build to install e.g.
                      x86-alex-release/R18-1655.0.0-a1-b1584.
        @param pool: Specify the pool of machines to use for scheduling
                purposes.
        @param devserver: an instance of a devserver to use to complete this
                  call.
        @param record: callable that records job status.
               prototype:
                 record(base_job.status_log_entry)
        @param check_hosts: require appropriate hosts to be available now.
        @param tests_to_skip: a list output parameter.  After execution, this
                              contains a list of control files not to run.
        @param dependencies: test-name-indexed dict of labels, e.g.
                             {'test1': ['label1', 'label2']}
                             Defaults to trivial set of dependencies, to cope
                             with builds that have no dependency information.

        @param num: the maximum number of devices to reimage.
        @param suite_job_id: Job id that will act as parent id to all sub jobs.
                     Default: None
        @return True if we succeed to kick off reimage jos, false if we can't.
        """

        if not num:
            num = tools.sharding_factor()

        begin_time_str = datetime.datetime.now().strftime(job_status.TIME_FMT)
        logging.debug("scheduling reimaging across at most %d machines", num)

        self._ensure_version_label(self._version_prefix + build)

        try:
            # Figure out what kind of hosts we need to grab.
            per_test_specs = self._build_host_specs_from_dependencies(
                self._board_label, pool, dependencies)

            # Pick hosts to use, make sure we have enough (if needed).
            self._to_reimage = self._build_host_group(
                set(per_test_specs.values()), num, check_hosts)

            # Determine which, if any, tests can't be run on the hosts we found.
            tests_to_skip.extend(
                self._discover_unrunnable_tests(per_test_specs,
                        self._to_reimage.unsatisfied_specs))
            for test_name in tests_to_skip:
                Status('TEST_NA', test_name, 'Unsatisfiable DEPENDENCIES',
                       begin_time_str=begin_time_str).record_all(record)

            # Schedule job and record job metadata.
            self._canary_job = self._schedule_reimage_job(
                {'image_name':build}, self._to_reimage, devserver,
                suite_job_id=suite_job_id)

            self._record_job_if_possible(Reimager.JOB_NAME, self._canary_job)
            logging.info('Created re-imaging job: %d', self._canary_job.id)

            return True

        except error.InadequateHostsException as e:
            logging.warning(e)
            Status('WARN', Reimager.JOB_NAME, str(e),
                   begin_time_str=begin_time_str).record_all(record)
            return False

        except Exception as e:
            # catch Exception so we record the job as terminated no matter what.
            import traceback
            logging.error(traceback.format_exc())
            logging.error(e)

            Status('ERROR', Reimager.JOB_NAME, str(e),
                   begin_time_str=begin_time_str).record_all(record)
            return False


    def wait(self, build, pool, record, check_hosts,
                tests_to_skip,
                dependencies={'':[]},
                scheduled_tests=[],
                timeout_mins=DEFAULT_TRY_JOB_TIMEOUT_MINS):
        #pylint: disable-msg=C0111
        """
        Synchronously wait on reimages to finish.

        If any machines fail that cause needed DEPENDENCIES to not be
        available, we also error out all of the now-unrunnable tests.

        @param build: the build being installed e.g.
                      x86-alex-release/R18-1655.0.0-a1-b1584.
        @param pool: Specify the pool of machines to use for scheduling
                purposes.
        @param record: callable that records job status.
               prototype:
                 record(base_job.status_log_entry)
        @param check_hosts: require appropriate hosts to be available now.
        @param tests_to_skip: DEPRECATED
        @param dependencies: DEPRECATED
        @param scheduled_tests: A list of ControlData objects corresponding to
                                all tests that were scheduled as part of the
                                same suite as this Reimage job. Used to
                                determine which unsatisfied-dependency-jobs
                                should be considered ERRORs, and which merely
                                WARNings. Defaults to [], in which case no
                                unsatisfied-dependency warnings or errors will
                                be logged.
        @param timeout_mins: Amount of time in mins to wait before timing out
                             this reimage attempt.

        @return True if at least one reimaging jobs succeed, False if they all
                fail or at least one is aborted.
        """
        begin_time_str = datetime.datetime.now().strftime(job_status.TIME_FMT)
        try:
            # We need to keep track of the timeout for tryjobs ourself. The
            # scheduler's timeout only applies to a job once it hits the
            # 'Running' state, and we want a timeout that enforces
            # 'Queued' + 'Running' < Timeout.
            start_time = datetime.datetime.utcnow()
            if not job_status.wait_for_jobs_to_start(self._afe,
                    [self._canary_job], start_time=start_time,
                    wait_timeout_mins=timeout_mins):
                raise error.ReimageAbortedException(
                    'Try job was aborted, timed out while waiting for hosts to'
                    ' start reimaging.')
            logging.debug('Re-imaging job running.')

            if not job_status.wait_for_jobs_to_finish(
                    self._afe, [self._canary_job], start_time=start_time,
                    wait_timeout_mins=timeout_mins):
                logging.error('Try job was aborted, timed out while waiting '
                              'for hosts to finish reimaging.')

            logging.debug('Re-imaging job finished.')

            if job_status.check_job_abort_status(self._afe, [self._canary_job]):
                raise error.ReimageAbortedException(
                        'Try job was aborted and not enough hosts completed'
                        'reimaging.')

            logging.debug('Gathering per_host_results.')
            results = job_status.gather_per_host_results(self._afe,
                                                         self._tko,
                                                         [self._canary_job],
                                                         Reimager.JOB_NAME+'-')

            self._reimaged_hosts[build] = results.keys()

        except error.ReimageAbortedException as e:
            logging.error('Try job aborted, recording ABORT and exiting.')
            Status('ABORT', Reimager.JOB_NAME, str(e),
                   begin_time_str=begin_time_str).record_all(record)
            return False

        except Exception as e:
            # catch Exception so we record the job as terminated no matter what.
            import traceback
            logging.error(traceback.format_exc())
            logging.error(e)

            Status('ERROR', Reimager.JOB_NAME, str(e),
                   begin_time_str=begin_time_str).record_all(record)
            return False

        should_continue = job_status.check_and_record_reimage_results(
            results, self._to_reimage, record)

        # Currently, this leads to us skipping even tests with no DEPENDENCIES
        # in certain cases: http://crosbug.com/34635
        dep_dictionary = {control_file: control_file.dependencies for
                          control_file in scheduled_tests}
        per_key_specs = self._build_host_specs_from_dependencies(
            self._board_label, pool, dep_dictionary)
        doomed_tests = self._discover_unrunnable_tests(per_key_specs,
            self._to_reimage.doomed_specs)
        for control_file in doomed_tests:
            if control_file.experimental:
                status = 'WARN'
                prefix = '(Experimental test) '
            else:
                status = 'ERROR'
                prefix = ''

            Status(status, control_file.name,
                   prefix + 'Failed to reimage machine with appropriate '
                   'labels.', begin_time_str=begin_time_str).record_all(record)

        return should_continue


    def abort(self):
        """
        Abort all scheduled reimage jobs.
        """
        if self._canary_job:
            self._afe.run('abort_host_queue_entries', job=self._canary_job.id)


    @property
    def version_prefix(self):
        """Report version prefix associated with this reimaging job."""
        return self._version_prefix


    def _build_host_specs_from_dependencies(self, board, pool, deps):
        """
        Return a dict of {key: HostSpec}, given some test dependencies.

        Given a dict of keys (of any type) mapping to dependency label lists,
        build and return a dict mapping each test to an appropriate HostSpec
        -- an object that specifies the kind of host needed to run the
        key-specified test in the suite.

        @param board: which kind of devices to reimage.
        @param pool: the pool of machines to use for scheduling purposes.
        @param deps: arbitrary-key-indexed dict of labels, e.g.
                     {'test1': ['label1', 'label2']} or
                     {ControlData(...): ['label1', 'label2']}
        @returns: dict of form {key: HostSpecs}, where keys match those
                  passed in deps parameter

        """
        base = [l for l in [board, pool] if l is not None]
        return dict(
            [(key, HostSpec(base, d)) for key, d in deps.iteritems()])


    def _build_host_group(self, host_specs, num, require_usable_hosts=True):
        """
        Given a list of HostSpec objects, build an appropriate HostGroup.

        Given a list of HostSpec objects, try to build a HostGroup that
        statisfies them all and contains num hosts.  If all can be satisfied
        with fewer than num hosts, log a warning and continue.  The caller
        can choose whether to check that we have enough currently usable hosts
        to satisfy the given requirements by passing True for check_hosts.

        @param host_specs: an iterable of HostSpecs.
        @param require_usable_hosts: require appropriate hosts to be available
                                     now.
        @param num: the maximum number of devices to reimage.
        @return a HostGroup derived from the provided HostSpec(s).
        @raises error.InadequateHostsException if there are more HostSpecs
                greater than the number of hosts requested.
        @raises error.NoHostsException if we find no usable hosts at all.
        """
        if len([s for s in host_specs if not s.is_trivial]) > num:
            raise error.InadequateHostsException(
                '%d hosts cannot satisfy dependencies %r' % (num, host_specs))

        hosts_per_spec = self._gather_hosts_from_host_specs(host_specs)
        if host_spec.is_simple_list(host_specs):
            spec, hosts = host_spec.simple_get_spec_and_hosts(
                host_specs, hosts_per_spec)
            if require_usable_hosts and not filter(tools.is_usable, hosts):
                raise error.NoHostsException('All hosts with %r are dead!' %
                                             spec)
            return MetaHostGroup(spec.labels, num)
        else:
            return self._choose_hosts(hosts_per_spec, num,
                                      require_usable_hosts)


    def _gather_hosts_from_host_specs(self, specs):
        """
        Given an iterable of HostSpec objets, find all hosts that satisfy each.

        @param specs: an iterable of HostSpecs.
        @return a dict of {HostSpec: [list, of, hosts]}
        """
        return dict(
            [(s, self._afe.get_hosts(multiple_labels=s.labels)) for s in specs])


    def _choose_hosts(self, hosts_per_spec, num, require_usable_hosts=True):
        """
        For each (spec, host_list) pair, choose >= 1 of the 'best' hosts.

        If picking one of each does not get us up to num total hosts, fill out
        the list with more hosts that fit the 'least restrictive' host_spec.

        Hosts are stack-ranked by availability.  So, 'Ready' is the best,
        followed by anything else that can pass the tools.is_usable() predicate
        below.  If require_usable_hosts is False, we'll fall all the way back to
        currently unusable hosts.

        @param hosts_per_spec: {HostSpec: [list, of, hosts]}.
        @param num: how many devices to reimage.
        @param require_usable_hosts: only return hosts currently in a usable
                                     state.
        @return a HostGroup encoding the set of hosts to reimage.
        @raises error.NoHostsException if we find no usable hosts at all.
        """
        ordered_specs = host_spec.order_by_complexity(hosts_per_spec.keys())
        hosts_to_use = ExplicitHostGroup()
        for spec in ordered_specs:
            if hosts_to_use.size() == num:
                break  # Bail early if we've already exhausted our allowance.
            to_check = filter(lambda h: not hosts_to_use.contains_host(h),
                              hosts_per_spec[spec])
            chosen = tools.get_random_best_host(self._afe, to_check,
                                                require_usable_hosts)
            hosts_to_use.add_host_for_spec(spec, chosen)

        if hosts_to_use.size() == 0:
            raise error.NoHostsException('All hosts for %r are dead!' %
                                         ordered_specs)

        # fill out the set with DUTs that fit the least complex HostSpec.
        simplest_spec = ordered_specs[-1]
        for i in xrange(num - hosts_to_use.size()):
            to_check = filter(lambda h: not hosts_to_use.contains_host(h),
                              hosts_per_spec[simplest_spec])
            chosen = tools.get_random_best_host(self._afe, to_check,
                                                require_usable_hosts)
            hosts_to_use.add_host_for_spec(simplest_spec, chosen)

        if hosts_to_use.unsatisfied_specs:
            logging.warn('Could not find %d hosts to use; '
                         'unsatisfied dependencies: %r.',
                         num, hosts_to_use.unsatisfied_specs)
        elif num > hosts_to_use.size():
            logging.warn('Could not find %d hosts to use, '
                         'but dependencies are satisfied.', num)

        return hosts_to_use


    def _discover_unrunnable_tests(self, per_key_specs, bad_specs):
        """
        Exclude tests by name based on a blacklist of bad HostSpecs.

        @param per_key_specs: a dictionary from of type {key: HostSpec}
                              where key is any hashable type.
        @param bad_specs: iterable of HostSpec whose associated tests should
                          be excluded.
        @return iterable of keys that are associated with bad_specs.
        """
        return [n for n, s in per_key_specs.iteritems() if s in bad_specs]


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
            if not host.startswith('hostless'):
                self._clear_build_state(host)


    def _clear_build_state(self, machine):
        """
        Clear all build-specific labels, attributes from the target.

        @param machine: the host to clear labels, attributes from.
        """
        self._afe.set_host_attribute(constants.JOB_REPO_URL, None,
                                     hostname=machine)


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


    def _ensure_version_label(self, name):
        """
        Ensure that a label called exists in the autotest DB.

        @param name:the label to check for/create.
        """
        try:
            self._afe.create_label(name=name)
        except proxy.ValidationError as ve:
            if ('name' in ve.problem_keys and
                'This value must be unique' in ve.problem_keys['name']):
                logging.debug('Version label %s already exists', name)
            else:
                raise ve


    def _schedule_reimage_job_base(self, host_group, params,
                                   suite_job_id=None):
        """
        Schedules the reimaging of hosts in a host group.

        Sends an RPC to the autotest frontend to enqueue reimaging jobs on
        |num_machines| devices of type |board|.

        @param: host_group, a HostGroup object representing the set of hosts
                to be reimaged.

        @param params: a dictionary where keys and values are strings to be
                injected as assignments into the scheduling autotest control
                file. The dictionary contains reimaging type specific
                information.
        @param suite_job_id: Job id that will act as parent id to all sub jobs.
                             Default: None
        @return a frontend.Job object for the reimaging job we scheduled.
        """
        params['image_url'] = self._url_pattern % (
            params['devserver_url'], params['image_name'])

        control_file = tools.inject_vars(
            params,
            self._cf_getter.get_control_file_contents_by_name(
                self._control_file))

        return self._afe.create_job(control_file=control_file,
                                     name=params['image_name'] + '-try',
                                     control_type='Server',
                                     priority='Low',
                                     parent_job_id=suite_job_id,
                                     **host_group.as_args())


    def _schedule_reimage_job(self, params, host_group, devserver,
                              suite_job_id=None):
        """
        This is meant to be overridden by a subclass to do whatever special
        setup work is required before calling into _schedule_reimage_job_base.

        @param params: a dictionary where keys and values are strings, to be
                  injected into the reimaging job control file as variable
                  assignments. By the time this function is invoked the
                  dictionary contains one element, the name of the build to
                  use for reimaging.
        @param host_group: the HostGroup to be used for this reimaging job.
        @param devserver: an instance of devserver that DUTs should use to get
                  build artifacts from.
        @param suite_job_id: Job id that will act as parent id to all sub jobs.
           Default: None

        @return a frontend.Job object for the scheduled reimaging job.
        """
        raise NotImplementedError()


@reimage_type(constants.REIMAGE_TYPE_OS)
class OsReimager(Reimager):
    """
    A class that can run jobs to reimage Chrome OS on devices.

    See attributes' description in the parent class docstring.
    """

    def __init__(self, autotest_dir, board, afe=None, tko=None,
                 results_dir=None):
        """Constructor

        See parameters' description in the parent class constructor docstring.
        """

        super(OsReimager, self).__init__(autotest_dir, board, afe=afe, tko=tko,
                                         results_dir=results_dir)
        self._version_prefix = constants.VERSION_PREFIX
        self._control_file = 'autoupdate'
        self._url_pattern = tools.image_url_pattern()

    def _schedule_reimage_job(self, params, host_group, devserver,
                              suite_job_id=None):
        """Schedules the reimaging of a group of hosts with a Chrome OS image.

        Adds a parameter to the params dictionary and invokes the base class
        reimaging function, which sends an RPC to the autotest frontend to
        enqueue reimaging jobs on hosts in the host_group.

        @param params: a dictionary where keys and values are strings, to be
                  injected into the reimaging job control file as variable
                  assignments. By the time this function is invoked the
                  dictionary contains one element, the name of the build to
                  use for reimaging.
        @param host_group: the HostGroup to be used for this reimaging job.
        @param devserver: an instance of devserver that DUTs should use to get
                  build artifacts from.
        @param suite_job_id: Job id that will act as parent id to all sub jobs.
                             Default: None

        @return a frontend.Job object for the scheduled reimaging job.

        """
        params['devserver_url'] = devserver.url()
        return self._schedule_reimage_job_base(host_group, params,
                                               suite_job_id=suite_job_id)


@reimage_type(constants.REIMAGE_TYPE_FIRMWARE)
class FwReimager(Reimager):
    """
    A class that can run jobs to reimage firmware on devices.

    See attributes' description in the parent class docstring.
    """


    def __init__(self, autotest_dir, board, afe=None, tko=None,
                 results_dir=None):
        """Constructor

        See parameters' description in the parent class constructor docstring.
        """

        super(FwReimager, self).__init__(autotest_dir, board, afe=afe, tko=tko,
                                         results_dir=results_dir)
        self._version_prefix = constants.FW_VERSION_PREFIX
        self._control_file = 'fwupdate'
        self._url_pattern = tools.firmware_url_pattern()


    def _schedule_reimage_job(self, params, host_group, devserver,
                              suite_job_id=None):
        """Schedules the reimaging of a group of hosts with a Chrome OS image.

        Makes sure that the artifacts download has been completed (firmware
        tarball is downloaded asynchronously), then a few parameters to the
        params dictionary and invokes the base class reimaging function, which
        sends an RPC to the autotest frontend to enqueue reimaging jobs on
        hosts in the host_group.

        @param params: a dictionary where keys and values are strings, to be
                  injected into the reimaging job control file as variable
                  assignments. By the time this function is invoked the
                  dictionary contains one element, the name of the build to
                  use for reimaging.
        @param host_group: the HostGroup to be used for this reimaging job.
        @param devserver: an instance of devserver that DUTs should use to get
                  build artifacts from.
        @param suite_job_id: Job id that will act as parent id to all sub jobs.
                             Default: None
        @return a frontend.Job object for the scheduled reimaging job.
        """
        # Ensures that the firmware tarball is staged.
        devserver.stage_artifacts(params['image_name'], ['firmware'])
        params['devserver_url'] = devserver.url()
        params['board'] = self._board_label.split(':')[-1]
        return self._schedule_reimage_job_base(host_group, params,
                                               suite_job_id=suite_job_id)
