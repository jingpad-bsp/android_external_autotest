#!/usr/bin/python
#pylint: disable-msg=C0111

# Copyright (c) 2014 The Chromium OS Authors. All rights reserved.
# Use of this source code is governed by a BSD-style license that can be
# found in the LICENSE file.

import collections

import common

from autotest_lib.client.common_lib import host_queue_entry_states
from autotest_lib.client.common_lib.test_utils import unittest
from autotest_lib.database import database_connection
from autotest_lib.frontend import setup_django_environment
from autotest_lib.frontend.afe import frontend_test_utils
from autotest_lib.frontend.afe import models
from autotest_lib.frontend.afe import rdb_model_extensions
from autotest_lib.scheduler import monitor_db
from autotest_lib.scheduler import monitor_db_functional_test
from autotest_lib.scheduler import scheduler_models
from autotest_lib.scheduler import rdb
from autotest_lib.scheduler import rdb_hosts
from autotest_lib.scheduler import rdb_lib
from autotest_lib.scheduler import rdb_requests
from autotest_lib.server.cros import provision


# Set for verbose table creation output.
_DEBUG = False


class DBHelper(object):
    """Utility class for updating the database."""

    def __init__(self):
        """Initialized django so it uses an in memory sqllite database."""
        self.database = (
            database_connection.TranslatingDatabase.get_test_database(
                translators=monitor_db_functional_test._DB_TRANSLATORS))
        self.database.connect(db_type='django')
        self.database.debug = _DEBUG


    @classmethod
    def get_labels(cls, **kwargs):
        """Get a label queryset based on the kwargs."""
        return models.Label.objects.filter(**kwargs)


    @classmethod
    def get_acls(cls, **kwargs):
        """Get an aclgroup queryset based on the kwargs."""
        return models.AclGroup.objects.filter(**kwargs)


    @classmethod
    def get_host(cls, **kwargs):
        """Get a host queryset based on the kwargs."""
        return models.Host.objects.filter(**kwargs)


    @classmethod
    def create_label(cls, name, **kwargs):
        label = cls.get_labels(name=name, **kwargs)
        return (models.Label.add_object(name=name, **kwargs)
                if not label else label[0])


    @classmethod
    def create_user(cls, name):
        user = models.User.objects.filter(login=name)
        return models.User.add_object(login=name) if not user else user[0]


    @classmethod
    def add_labels_to_host(cls, host, label_names=set([])):
        label_objects = set([])
        for label in label_names:
            label_objects.add(cls.create_label(label))
        host.labels.add(*label_objects)


    @classmethod
    def create_acl_group(cls, name):
        aclgroup = cls.get_acls(name=name)
        return (models.AclGroup.add_object(name=name)
                if not aclgroup else aclgroup[0])


    @classmethod
    def add_deps_to_job(cls, job, dep_names=set([])):
        label_objects = set([])
        for label in dep_names:
            label_objects.add(cls.create_label(label))
        job.dependency_labels.add(*label_objects)


    @classmethod
    def add_host_to_aclgroup(cls, host, aclgroup_names=set([])):
        for group_name in aclgroup_names:
            aclgroup = cls.create_acl_group(group_name)
            aclgroup.hosts.add(host)


    @classmethod
    def add_user_to_aclgroups(cls, username, aclgroup_names=set([])):
        user = cls.create_user(username)
        for group_name in aclgroup_names:
            aclgroup = cls.create_acl_group(group_name)
            aclgroup.users.add(user)


    @classmethod
    def create_host(cls, name, deps=set([]), acls=set([]), status='Ready',
                 locked=0, leased=0, protection=0, dirty=0):
        """Create a host.

        Also adds the appropriate labels to the host, and adds the host to the
        required acl groups.

        @param name: The hostname.
        @param kwargs:
            deps: The labels on the host that match job deps.
            acls: The aclgroups this host must be a part of.
            status: The status of the host.
            locked: 1 if the host is locked.
            leased: 1 if the host is leased.
            protection: Any protection level, such as Do Not Verify.
            dirty: 1 if the host requires cleanup.

        @return: The host object for the new host.
        """
        # TODO: Modify this to use the create host request once
        # crbug.com/350995 is fixed.
        host = models.Host.add_object(hostname=name, status=status, locked=locked,
                leased=leased, protection=protection)
        cls.add_labels_to_host(host, label_names=deps)
        cls.add_host_to_aclgroup(host, aclgroup_names=acls)

        # Though we can return the host object above, this proves that the host
        # actually got saved in the database. For example, this will return none if
        # save() wasn't called on the model.Host instance.
        return cls.get_host(hostname=name)[0]


    @classmethod
    def add_host_to_job(cls, host, job_id):
        """Add a host to the hqe of a job.

        @param host: An instance of the host model.
        @param job_id: The job to which we need to add the host.

        @raises ValueError: If the hqe for the job already has a host,
            or if the host argument isn't a Host instance.
        """
        hqe = models.HostQueueEntry.objects.get(job_id=job_id)
        if hqe.host:
            raise ValueError('HQE for job %s already has a host' % job_id)
        hqe.host = host
        hqe.save()


    @classmethod
    def add_host_to_job(cls, host, job_id):
        """Add a host to the hqe of a job.

        @param host: An instance of the host model.
        @param job_id: The job to which we need to add the host.

        @raises ValueError: If the hqe for the job already has a host,
            or if the host argument isn't a Host instance.
        """
        hqe = models.HostQueueEntry.objects.get(job_id=job_id)
        if hqe.host:
            raise ValueError('HQE for job %s already has a host' % job_id)
        hqe.host = host
        hqe.save()


    @classmethod
    def increment_priority(cls, job_id):
        job = models.Job.objects.get(id=job_id)
        job.priority = job.priority + 1
        job.save()


class AssignmentValidator(object):
    """Utility class to check that priority inversion doesn't happen. """


    @staticmethod
    def check_acls_deps(host, request):
        """Check if a host and request match by comparing acls and deps.

        @param host: A dictionary representing attributes of the host.
        @param request: A request, as defined in rdb_requests.

        @return True if the deps/acls of the request match the host.
        """
        # Unfortunately the hosts labels are labelnames, not ids.
        request_deps = set([l.name for l in
                models.Label.objects.filter(id__in=request.deps)])
        return (set(host['labels']).intersection(request_deps) == request_deps
                and set(host['acls']).intersection(request.acls))


    @staticmethod
    def find_matching_host_for_request(hosts, request):
        """Find a host from the given list of hosts, matching the request.

        @param hosts: A list of dictionaries representing host attributes.
        @param requetst: The unsatisfied request.

        @return: A host, if a matching host is found from the input list.
        """
        if not hosts or not request:
            return None
        for host in hosts:
            if AssignmentValidator.check_acls_deps(host, request):
                return host


    @staticmethod
    def sort_requests(requests):
        """Sort the requests by priority.

        @param requests: Unordered requests.

        @return: A list of requests ordered by priority.
        """
        return sorted(collections.Counter(requests).items(),
                key=lambda request: request[0].priority, reverse=True)


    @staticmethod
    def verify_priority(request_queue, result):
        requests = AssignmentValidator.sort_requests(request_queue)
        for request, count in requests:
            hosts = result.get(request)
            # The request was completely satisfied.
            if hosts and len(hosts) == count:
                continue
            # Go through all hosts given to lower priority requests and
            # make sure we couldn't have allocated one of them for this
            # unsatisfied higher priority request.
            lower_requests = requests[requests.index((request,count))+1:]
            for lower_request, count in lower_requests:
                if (lower_request.priority < request.priority and
                    AssignmentValidator.find_matching_host_for_request(
                            result.get(lower_request), request)):
                    raise ValueError('Priority inversion occured between '
                            'priorities %s and %s' %
                            (request.priority, lower_request.priority))


    @staticmethod
    def priority_checking_response_handler(request_manager):
        """Fake response handler wrapper for any request_manager.

        Check that higher priority requests get a response over lower priority
        requests, by re-validating all the hosts assigned to a lower priority
        request against the unsatisfied higher priority ones.

        @param request_manager: A request_manager as defined in rdb_lib.

        @raises ValueError: If priority inversion is detected.
        """
        # Fist call the rdb to make its decisions, then sort the requests
        # by priority and make sure unsatisfied requests higher up in the list
        # could not have been satisfied by hosts assigned to requests lower
        # down in the list.
        result = request_manager.api_call(request_manager.request_queue)
        if not result:
            raise ValueError('Expected results but got none.')
        AssignmentValidator.verify_priority(
                request_manager.request_queue, result)
        for hosts in result.values():
            for host in hosts:
                yield host


class BaseRDBTest(unittest.TestCase, frontend_test_utils.FrontendTestMixin):
    _config_section = 'AUTOTEST_WEB'


    def _release_unused_hosts(self):
        """Release all hosts unused by an active hqe. """
        self.host_scheduler.tick()


    def setUp(self):
        """Setup test conditions, including the sqllite database. """
        self.db_helper = DBHelper()
        self._database = self.db_helper.database

        # Runs syncdb setting up initial database conditions
        self._frontend_common_setup()

        # TODO: Remove once crbug.com/336934 is done.
        self.god.stub_with(monitor_db, '_db', self._database)
        self.god.stub_with(scheduler_models, '_db', self._database)
        self._dispatcher = monitor_db.Dispatcher()
        self.host_scheduler = self._dispatcher._host_scheduler
        self._release_unused_hosts()


    def tearDown(self):
        """Teardown the host/job database established through setUp. """
        self.god.unstub_all()
        self._database.disconnect()
        self._frontend_common_teardown()


    def create_job(self, user='autotest_system',
                   deps=set([]), acls=set([]), hostless_job=False,
                   priority=0, parent_job_id=None):
        """Create a job owned by user, with the deps and acls specified.

        This method is a wrapper around frontend_test_utils.create_job, that
        also takes care of creating the appropriate deps for a job, and the
        appropriate acls for the given user.

        @raises ValueError: If no deps are specified for a job, since all jobs
            need at least the metahost.
        @raises AssertionError: If no hqe was created for the job.

        @return: An instance of the job model associated with the new job.
        """
        # This is a slight hack around the implementation of
        # scheduler_models.is_hostless_job, even though a metahost is just
        # another label to the rdb.
        if not deps:
            raise ValueError('Need at least one dep for metahost')

        # TODO: This is a hack around the fact that frontend_test_utils still
        # need a metahost, but metahost is treated like any other label.
        metahost = DBHelper.create_label(list(deps)[0])
        job = self._create_job(metahosts=[metahost.id], priority=priority,
                owner=user, parent_job_id=parent_job_id)
        self.assert_(len(job.hostqueueentry_set.all()) == 1)

        DBHelper.add_deps_to_job(job, dep_names=list(deps)[1:])
        DBHelper.add_user_to_aclgroups(user, aclgroup_names=acls)
        return models.Job.objects.filter(id=job.id)[0]



    def assert_host_db_status(self, host_id):
        """Assert host state right after acquisition.

        Call this method to check the status of any host leased by the
        rdb before it has been assigned to an hqe. It must be leased and
        ready at this point in time.

        @param host_id: Id of the host to check.

        @raises AssertionError: If the host is either not leased or Ready.
        """
        host = models.Host.objects.get(id=host_id)
        self.assert_(host.leased)
        self.assert_(host.status == 'Ready')


    def check_hosts(self, host_iter):
        """Sanity check all hosts in the host_gen.

        @param host_iter: A generator/iterator of RDBClientHostWrappers.
            eg: The generator returned by rdb_lib.acquire_hosts. If a request
            was not satisfied this iterator can contain None.

        @raises AssertionError: If any of the sanity checks fail.
        """
        for host in host_iter:
            if host:
                self.assert_host_db_status(host.id)
                self.assert_(host.leased == 1)


    def create_suite(self, user='autotest_system', num=2, priority=0,
                     board='z', build='x'):
        """Create num jobs with the same parent_job_id, board, build, priority.

        @return: A dictionary with the parent job object keyed as 'parent_job'
            and all other jobs keyed at an index from 0-num.
        """
        jobs = {}
        # Create a hostless parent job without an hqe or deps. Since the
        # hostless job does nothing, we need to hand craft cros-version.
        parent_job = self._create_job(owner=user, priority=priority)
        jobs['parent_job'] = parent_job
        build = '%s:%s' % (provision.CROS_VERSION_PREFIX, build)
        for job_index in range(0, num):
            jobs[job_index] = self.create_job(user=user, priority=priority,
                                              deps=set([board, build]),
                                              parent_job_id=parent_job.id)
        return jobs


    def check_host_assignment(self, job_id, host_id):
        """Check is a job<->host assignment is valid.

        Uses the deps of a job and the aclgroups the owner of the job is
        in to see if the given host can be used to run the given job. Also
        checks that the host-job assignment has Not been made, but that the
        host is no longer in the available hosts pool.

        Use this method to check host assignements made by the rdb, Before
        they're handed off to the scheduler, since the scheduler.

        @param job_id: The id of the job to use in the compatibility check.
        @param host_id: The id of the host to check for compatibility.

        @raises AssertionError: If the job and the host are incompatible.
        """
        job = models.Job.objects.get(id=job_id)
        host = models.Host.objects.get(id=host_id)
        hqe = job.hostqueueentry_set.all()[0]

        # Confirm that the host has not been assigned, either to another hqe
        # or the this one.
        all_hqes = models.HostQueueEntry.objects.filter(host_id=host_id, complete=0)
        self.assert_(len(all_hqes) <= 1)
        self.assert_(hqe.host_id == None)
        self.assert_host_db_status(host_id)

        # Assert that all deps of the job are satisfied.
        job_deps = set([d.name for d in job.dependency_labels.all()])
        host_labels = set([l.name for l in host.labels.all()])
        self.assert_(job_deps.intersection(host_labels) == job_deps)

        # Assert that the owner of the job is in at least one of the
        # groups that owns the host.
        job_owner_aclgroups = set([job_acl.name for job_acl
                                   in job.user().aclgroup_set.all()])
        host_aclgroups = set([host_acl.name for host_acl
                              in host.aclgroup_set.all()])
        self.assert_(job_owner_aclgroups.intersection(host_aclgroups))


    def testAcquireLeasedHostBasic(self):
        """Test that acquisition of a leased host doesn't happen.

        @raises AssertionError: If the one host that satisfies the request
            is acquired.
        """
        job = self.create_job(deps=set(['a']))
        host = self.db_helper.create_host('h1', deps=set(['a']))
        host.leased = 1
        host.save()
        queue_entries = self._dispatcher._refresh_pending_queue_entries()
        hosts = list(rdb_lib.acquire_hosts(
            self.host_scheduler, queue_entries))
        self.assertTrue(len(hosts) == 1 and hosts[0] is None)


    def testAcquireLeasedHostRace(self):
        """Test behaviour when hosts are leased just before acquisition.

        If a fraction of the hosts somehow get leased between finding and
        acquisition, the rdb should just return the remaining hosts for the
        request to use.

        @raises AssertionError: If both the requests get a host successfully,
            since one host gets leased before the final attempt to lease both.
        """
        j1 = self.create_job(deps=set(['a']))
        j2 = self.create_job(deps=set(['a']))
        hosts = [self.db_helper.create_host('h1', deps=set(['a'])),
                 self.db_helper.create_host('h2', deps=set(['a']))]

        @rdb_hosts.return_rdb_host
        def local_find_hosts(host_query_maanger, deps, acls):
            """Return a predetermined list of hosts, one of which is leased."""
            h1 = models.Host.objects.get(hostname='h1')
            h1.leased = 1
            h1.save()
            h2 = models.Host.objects.get(hostname='h2')
            return [h1, h2]

        self.god.stub_with(rdb.AvailableHostQueryManager, 'find_hosts',
                           local_find_hosts)
        queue_entries = self._dispatcher._refresh_pending_queue_entries()
        hosts = list(rdb_lib.acquire_hosts(
            self.host_scheduler, queue_entries))
        self.assertTrue(len(hosts) == 2 and None in hosts)
        self.check_hosts(iter(hosts))


    def testHostReleaseStates(self):
        """Test that we will only release an unused host if it is in Ready.

        @raises AssertionError: If the host gets released in any other state.
        """
        host = self.db_helper.create_host('h1', deps=set(['x']))
        for state in rdb_model_extensions.AbstractHostModel.Status.names:
            host.status = state
            host.leased = 1
            host.save()
            self._release_unused_hosts()
            host = models.Host.objects.get(hostname='h1')
            self.assertTrue(host.leased == (state != 'Ready'))


    def testHostReleseHQE(self):
        """Test that we will not release a ready host if it's being used.

        @raises AssertionError: If the host is released even though it has
            been assigned to an active hqe.
        """
        # Create a host and lease it out in Ready.
        host = self.db_helper.create_host('h1', deps=set(['x']))
        host.status = 'Ready'
        host.leased = 1
        host.save()

        # Create a job and give its hqe the leased host.
        job = self.create_job(deps=set(['x']))
        self.db_helper.add_host_to_job(host, job.id)
        hqe = models.HostQueueEntry.objects.get(job_id=job.id)

        # Activate the hqe by setting its state.
        hqe.status = host_queue_entry_states.ACTIVE_STATUSES[0]
        hqe.save()

        # Make sure the hqes host isn't released, even if its in ready.
        self._release_unused_hosts()
        host = models.Host.objects.get(hostname='h1')
        self.assertTrue(host.leased == 1)


    def testBasicDepsAcls(self):
        """Test a basic deps/acls request.

        Make sure that a basic request with deps and acls, finds a host from
        the ready pool that has matching labels and is in a matching aclgroups.

        @raises AssertionError: If the request doesn't find a host, since the
            we insert a matching host in the ready pool.
        """
        deps = set(['a', 'b'])
        acls = set(['a', 'b'])
        self.db_helper.create_host('h1', deps=deps, acls=acls)
        job = self.create_job(user='autotest_system', deps=deps, acls=acls)
        queue_entries = self._dispatcher._refresh_pending_queue_entries()
        matching_host  = rdb_lib.acquire_hosts(
                self.host_scheduler, queue_entries).next()
        self.check_host_assignment(job.id, matching_host.id)
        self.assertTrue(matching_host.leased == 1)


    def testBadDeps(self):
        """Test that we find no hosts when only acls match.

        @raises AssertionError: If the request finds a host, since the only
            host in the ready pool will not have matching deps.
        """
        host_labels = set(['a'])
        job_deps = set(['b'])
        acls = set(['a', 'b'])
        self.db_helper.create_host('h1', deps=host_labels, acls=acls)
        job = self.create_job(user='autotest_system', deps=job_deps, acls=acls)
        queue_entries = self._dispatcher._refresh_pending_queue_entries()
        matching_host  = rdb_lib.acquire_hosts(
                self.host_scheduler, queue_entries).next()
        self.assert_(not matching_host)


    def testBadAcls(self):
        """Test that we find no hosts when only deps match.

        @raises AssertionError: If the request finds a host, since the only
            host in the ready pool will not have matching acls.
        """
        deps = set(['a'])
        host_acls = set(['a'])
        job_acls = set(['b'])
        self.db_helper.create_host('h1', deps=deps, acls=host_acls)

        # Create the job as a new user who is only in the 'b' and 'Everyone'
        # aclgroups. Though there are several hosts in the Everyone group, the
        # 1 host that has the 'a' dep isn't.
        job = self.create_job(user='new_user', deps=deps, acls=job_acls)
        queue_entries = self._dispatcher._refresh_pending_queue_entries()
        matching_host  = rdb_lib.acquire_hosts(
                self.host_scheduler, queue_entries).next()
        self.assert_(not matching_host)


    def testBasicPriority(self):
        """Test that priority inversion doesn't happen.

        Schedule 2 jobs with the same deps, acls and user, but different
        priorities, and confirm that the higher priority request gets the host.
        This confirmation happens through the AssignmentValidator.

        @raises AssertionError: If the un important request gets host h1 instead
            of the important request.
        """
        deps = set(['a', 'b'])
        acls = set(['a', 'b'])
        self.db_helper.create_host('h1', deps=deps, acls=acls)
        important_job = self.create_job(user='autotest_system',
                deps=deps, acls=acls, priority=2)
        un_important_job = self.create_job(user='autotest_system',
                deps=deps, acls=acls, priority=0)
        queue_entries = self._dispatcher._refresh_pending_queue_entries()

        self.god.stub_with(rdb_requests.BaseHostRequestManager, 'response',
                AssignmentValidator.priority_checking_response_handler)
        self.check_hosts(rdb_lib.acquire_hosts(
            self.host_scheduler, queue_entries))


    def testPriorityLevels(self):
        """Test that priority inversion doesn't happen.

        Increases a job's priority and makes several requests for hosts,
        checking that priority inversion doesn't happen.

        @raises AssertionError: If the unimportant job gets h1 while it is
            still unimportant, or doesn't get h1 while after it becomes the
            most important job.
        """
        deps = set(['a', 'b'])
        acls = set(['a', 'b'])
        self.db_helper.create_host('h1', deps=deps, acls=acls)

        # Create jobs that will bucket differently and confirm that jobs in an
        # earlier bucket get a host.
        first_job = self.create_job(user='autotest_system', deps=deps, acls=acls)
        important_job = self.create_job(user='autotest_system', deps=deps,
                acls=acls, priority=2)
        deps.pop()
        unimportant_job = self.create_job(user='someother_system', deps=deps,
                acls=acls, priority=1)
        queue_entries = self._dispatcher._refresh_pending_queue_entries()

        self.god.stub_with(rdb_requests.BaseHostRequestManager, 'response',
                AssignmentValidator.priority_checking_response_handler)
        self.check_hosts(rdb_lib.acquire_hosts(
            self.host_scheduler, queue_entries))

        # Elevate the priority of the unimportant job, so we now have
        # 2 jobs at the same priority.
        self.db_helper.increment_priority(job_id=unimportant_job.id)
        queue_entries = self._dispatcher._refresh_pending_queue_entries()
        self._release_unused_hosts()
        self.check_hosts(rdb_lib.acquire_hosts(
            self.host_scheduler, queue_entries))

        # Prioritize the first job, and confirm that it gets the host over the
        # jobs that got it the last time.
        self.db_helper.increment_priority(job_id=unimportant_job.id)
        queue_entries = self._dispatcher._refresh_pending_queue_entries()
        self._release_unused_hosts()
        self.check_hosts(rdb_lib.acquire_hosts(
            self.host_scheduler, queue_entries))


    def testFrontendJobScheduling(self):
        """Test that basic frontend job scheduling.

        @raises AssertionError: If the received and requested host don't match,
            or the mis-matching host is returned instead.
        """
        deps = set(['x', 'y'])
        acls = set(['a', 'b'])

        # Create 2 frontend jobs and only one matching host.
        matching_job = self.create_job(acls=acls, deps=deps)
        matching_host = self.db_helper.create_host('h1', acls=acls, deps=deps)
        mis_matching_job = self.create_job(acls=acls, deps=deps)
        mis_matching_host = self.db_helper.create_host(
                'h2', acls=acls, deps=deps.pop())
        self.db_helper.add_host_to_job(matching_host, matching_job.id)
        self.db_helper.add_host_to_job(mis_matching_host, mis_matching_job.id)

        # Check that only the matching host is returned, and that we get 'None'
        # for the second request.
        queue_entries = self._dispatcher._refresh_pending_queue_entries()
        hosts = list(rdb_lib.acquire_hosts(self.host_scheduler, queue_entries))
        self.assertTrue(len(hosts) == 2 and None in hosts)
        returned_host = [host for host in hosts if host].pop()
        self.assertTrue(matching_host.id == returned_host.id)


    def testFrontendJobPriority(self):
        """Test that frontend job scheduling doesn't ignore priorities.

        @raises ValueError: If the priorities of frontend jobs are ignored.
        """
        board = 'x'
        high_priority = self.create_job(priority=2, deps=set([board]))
        low_priority = self.create_job(priority=1, deps=set([board]))
        host = self.db_helper.create_host('h1', deps=set([board]))
        self.db_helper.add_host_to_job(host, low_priority.id)
        self.db_helper.add_host_to_job(host, high_priority.id)

        queue_entries = self._dispatcher._refresh_pending_queue_entries()

        def local_response_handler(request_manager):
            """Confirms that a higher priority frontend job gets a host.

            @raises ValueError: If priority inversion happens and the job
                with priority 1 gets the host instead.
            """
            result = request_manager.api_call(request_manager.request_queue)
            if not result:
                raise ValueError('Excepted the high priority request to '
                                 'get a host, but the result is empty.')
            for request, hosts in result.iteritems():
                if request.priority == 1:
                    raise ValueError('Priority of frontend job ignored.')
                if len(hosts) > 1:
                    raise ValueError('Multiple hosts returned against one '
                                     'frontend job scheduling request.')
                yield hosts[0]

        self.god.stub_with(rdb_requests.BaseHostRequestManager, 'response',
                           local_response_handler)
        self.check_hosts(rdb_lib.acquire_hosts(
            self.host_scheduler, queue_entries))


    def testSuiteOrderedHostAcquisition(self):
        """Test that older suite jobs acquire hosts first.

        Make sure older suite jobs get hosts first, but not at the expense of
        higher priority jobs.

        @raises ValueError: If unexpected acquisitions occur, eg:
            suite_job_2 acquires the last 2 hosts instead of suite_job_1.
            isolated_important_job doesn't get any hosts.
            Any job acquires more hosts than necessary.
        """
        board = 'x'
        suite_without_dep = self.create_suite(num=2, priority=0, board=board)
        suite_with_dep = self.create_suite(num=1, priority=0, board=board)
        DBHelper.add_deps_to_job(suite_with_dep[0], dep_names=list('y'))
        isolated_important_job = self.create_job(priority=3, deps=set([board]))

        for i in range(0, 3):
            DBHelper.create_host('h%s' % i, deps=set([board, 'y']))

        queue_entries = self._dispatcher._refresh_pending_queue_entries()

        def local_response_handler(request_manager):
            """Reorder requests and check host acquisition.

            @raises ValueError: If unexpected/no acquisitions occur.
            """
            if any([request for request in request_manager.request_queue
                    if request.parent_job_id is None]):
                raise ValueError('Parent_job_id can never be None.')

            # This will result in the ordering:
            # [suite_2_1, suite_1_*, suite_1_*, isolated_important_job]
            # The priority scheduling order should be:
            # [isolated_important_job, suite_1_*, suite_1_*, suite_2_1]
            # Since:
            #   a. the isolated_important_job is the most important.
            #   b. suite_1 was created before suite_2, regardless of deps
            disorderly_queue = sorted(request_manager.request_queue,
                    key=lambda r: -r.parent_job_id)
            request_manager.request_queue = disorderly_queue
            result = request_manager.api_call(request_manager.request_queue)
            if not result:
                raise ValueError('Expected results but got none.')

            # Verify that the isolated_important_job got a host, and that the
            # first suite got both remaining free hosts.
            for request, hosts in result.iteritems():
                if request.parent_job_id == 0:
                    if len(hosts) > 1:
                        raise ValueError('First job acquired more hosts than '
                                'necessary. Response map: %s' % result)
                    continue
                if request.parent_job_id == 1:
                    if len(hosts) < 2:
                        raise ValueError('First suite job requests were not '
                                'satisfied. Response_map: %s' % result)
                    continue
                # The second suite job got hosts instead of one of
                # the others. Eitherway this is a failure.
                raise ValueError('Unexpected host acquisition '
                        'Response map: %s' % result)
            yield None

        self.god.stub_with(rdb_requests.BaseHostRequestManager, 'response',
                           local_response_handler)
        list(rdb_lib.acquire_hosts(self.host_scheduler, queue_entries))

