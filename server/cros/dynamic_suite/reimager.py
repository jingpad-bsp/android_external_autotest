# Copyright (c) 2012 The Chromium OS Authors. All rights reserved.
# Use of this source code is governed by a BSD-style license that can be
# found in the LICENSE file.


import compiler, datetime, hashlib, logging, os

import common

from autotest_lib.client.common_lib import control_data, global_config
from autotest_lib.client.common_lib import error, utils
from autotest_lib.client.common_lib.cros import dev_server
from autotest_lib.server.cros.dynamic_suite import constants
from autotest_lib.server.cros.dynamic_suite import control_file_getter
from autotest_lib.server.cros.dynamic_suite import frontend_wrappers
from autotest_lib.server.cros.dynamic_suite import host_lock_manager, job_status
from autotest_lib.server.cros.dynamic_suite import tools
from autotest_lib.server.cros.dynamic_suite.job_status import Status
from autotest_lib.server import frontend
from autotest_lib.frontend.afe.json_rpc import proxy


class Reimager(object):
    """
    A class that can run jobs to reimage devices.

    @var _afe: a frontend.AFE instance used to talk to autotest.
    @var _tko: a frontend.TKO instance used to query the autotest results db.
    @var _cf_getter: a ControlFileGetter used to get the AU control file.
    """

    JOB_NAME = 'try_new_image'


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


    def attempt(self, build, board, pool, record, check_hosts,
                manager, num=None):
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
        @param manager: an as-yet-unused HostLockManager instance to handle
                        locking DUTs that we decide to reimage.
        @param num: how many devices to reimage.
        @return True if all reimaging jobs succeed, false otherwise.
        """
        if not num:
            num = tools.sharding_factor()
        logging.debug("scheduling reimaging across %d machines", num)
        begin_time_str = datetime.datetime.now().strftime(job_status.TIME_FMT)
        try:
            self._ensure_version_label(constants.VERSION_PREFIX + build)

            if check_hosts:
                # TODO make DEPENDENCIES-aware
                self._ensure_enough_hosts(board, pool, num)

            # Schedule job and record job metadata.
            # TODO make DEPENDENCIES-aware
            canary_job = self._schedule_reimage_job(build, board, pool, num)
            self._record_job_if_possible(Reimager.JOB_NAME, canary_job)
            logging.info('Created re-imaging job: %d', canary_job.id)

            job_status.wait_for_jobs_to_start(self._afe, [canary_job])
            logging.debug('Re-imaging job running.')

            hosts = job_status.wait_for_and_lock_job_hosts(self._afe,
                                                           [canary_job],
                                                           manager)
            logging.info('%r locked for reimaging.', hosts)

            job_status.wait_for_jobs_to_finish(self._afe, [canary_job])
            logging.debug('Re-imaging job finished.')

            # Gather job results.
            results = self.get_results(canary_job)
            self._reimaged_hosts[build] = results.keys()

        except error.InadequateHostsException as e:
            logging.warning(e)
            Status('WARN', Reimager.JOB_NAME, str(e),
                   begin_time_str=begin_time_str).record_all(record)
            return False
        except Exception as e:
            # catch Exception so we record the job as terminated no matter what.
            logging.error(e)
            Status('ERROR', Reimager.JOB_NAME, str(e),
                   begin_time_str=begin_time_str).record_all(record)
            return False

        return job_status.record_and_report_results(results.values(), record)


    def get_results(self, canary_job):
        """
        Gather results for |canary_job|, in a map of Statuses indexed by host.

        A host's results will be named Reimager.JOB_NAME-<host> in the map, e.g.
          {'chromeos2-rack1': Status('GOOD', 'try_new_image-chromeos2-rack1')}

        @param canary_job: a completed frontend.Job
        @return a map of hostname: job_status.Status objects.
        """
        return job_status.gather_per_host_results(self._afe,
                                                  self._tko,
                                                  [canary_job],
                                                  Reimager.JOB_NAME + '-')


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
        image_url = tools.image_url_pattern() % (
            dev_server.DevServer.devserver_url_for_build(build), build)
        control_file = tools.inject_vars(
            dict(image_url=image_url, image_name=build),
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
