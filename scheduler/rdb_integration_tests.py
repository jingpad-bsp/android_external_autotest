#!/usr/bin/python
#pylint: disable-msg=C0111

# Copyright (c) 2014 The Chromium OS Authors. All rights reserved.
# Use of this source code is governed by a BSD-style license that can be
# found in the LICENSE file.

import collections

import common
from autotest_lib.frontend import setup_django_environment
from autotest_lib.frontend.afe import frontend_test_utils
from autotest_lib.client.common_lib.test_utils import unittest
from autotest_lib.database import database_connection
from autotest_lib.frontend.afe import models
from autotest_lib.scheduler import monitor_db
from autotest_lib.scheduler import monitor_db_functional_test
from autotest_lib.scheduler import scheduler_models
from autotest_lib.scheduler import rdb_lib, rdb_requests

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
    def create_label(cls, name):
        label = models.Label.objects.filter(name=name)
        return models.Label.add_object(name=name) if not label else label[0]


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
    def add_deps_to_job(cls, job, dep_names=set([])):
        label_objects = set([])
        for label in dep_names:
            label_objects.add(cls.create_label(label))
        job.dependency_labels.add(*label_objects)


    @classmethod
    def create_acl_group(cls, name):
        aclgroup = models.AclGroup.objects.filter(name=name)
        return (models.AclGroup.add_object(name=name)
                if not aclgroup else aclgroup[0])


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
        return models.Host.objects.filter(hostname=name)[0]


    @classmethod
    def increment_priority(cls, job_id):
        job = models.Job.objects.get(id=job_id)
        job.priority = job.priority + 1
        job.save()


class PriorityAssignmentValidator(object):
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
            if PriorityAssignmentValidator.check_acls_deps(host, request):
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
        requests = PriorityAssignmentValidator.sort_requests(
                request_manager.request_queue)
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
                if (PriorityAssignmentValidator.find_matching_host_for_request(
                    result.get(lower_request), request)):
                    raise ValueError('Priority inversion occured between '
                            'priorities %s and %s' %
                            (request.priority, lower_request.priority))
        # Though we've confirmed behavior, the rdb_lib method that is using this
        # request manager needs to exit cleanly.
        yield None


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
        self._database.disconnect()
        self._frontend_common_teardown()


    def create_job(self, user='autotest_system',
                   deps=set([]), acls=set([]), priority=0):
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
        metahost = DBHelper.create_label(list(deps)[0])
        job = self._create_job(metahosts=[metahost.id], priority=priority,
                owner=user)
        self.assert_(len(job.hostqueueentry_set.all()) == 1)
        DBHelper.add_deps_to_job(job, dep_names=list(deps)[1:])
        DBHelper.add_user_to_aclgroups(user, aclgroup_names=acls)
        return models.Job.objects.filter(id=job.id)[0]


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
            This will happen
        """
        job = models.Job.objects.get(id=job_id)
        host = models.Host.objects.get(id=host_id)
        hqe = job.hostqueueentry_set.all()[0]

        # Confirm that the host has not been assigned, either to another hqe
        # or the this one.
        all_hqes = models.HostQueueEntry.objects.filter(host_id=host_id, complete=0)
        self.assert_(len(all_hqes) <= 1)
        self.assert_(hqe.host_id == None)

        # Assert basic host status.
        self.assert_(host.leased)
        self.assert_(host.status == 'Ready')

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


    def testBasicDepsAcls(self):
        """Test a basic deps/acls request.

        Make sure that a basic request with deps and acls, finds a host from
        the ready pool that has matching labels and is in a matching aclgroups.

        @raises AssertionError: If the request doesn't find a host, since the
            we insert a matching host in the ready pool.
        """
        deps = set(['a', 'b'])
        acls = set(['a', 'b'])
        DBHelper.create_host('h1', deps=deps, acls=acls)
        job = self.create_job(user='autotest_system', deps=deps, acls=acls)
        queue_entries = self._dispatcher._refresh_pending_queue_entries()
        matching_host  = rdb_lib.acquire_hosts(
                self.host_scheduler, queue_entries).next()
        self.check_host_assignment(job.id, matching_host.id)


    def testBadDeps(self):
        """Test that we find no hosts when only acls match.

        @raises AssertionError: If the request finds a host, since the only
            host in the ready pool will not have matching deps.
        """
        host_labels = set(['a'])
        job_deps = set(['b'])
        acls = set(['a', 'b'])
        DBHelper.create_host('h1', deps=host_labels, acls=acls)
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
        DBHelper.create_host('h1', deps=deps, acls=host_acls)

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
        This confirmation happens through the PriorityAssignmentValidator.

        @raises AssertionError: If the un important request gets host h1 instead
            of the important request.
        """
        deps = set(['a', 'b'])
        acls = set(['a', 'b'])
        DBHelper.create_host('h1', deps=deps, acls=acls)
        important_job = self.create_job(user='autotest_system',
                deps=deps, acls=acls, priority=2)
        un_important_job = self.create_job(user='autotest_system',
                deps=deps, acls=acls, priority=0)
        queue_entries = self._dispatcher._refresh_pending_queue_entries()

        self.god.stub_with(rdb_requests.BaseHostRequestManager, 'response',
                PriorityAssignmentValidator.priority_checking_response_handler)
        list(rdb_lib.acquire_hosts(self.host_scheduler, queue_entries))


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
        DBHelper.create_host('h1', deps=deps, acls=acls)

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
                PriorityAssignmentValidator.priority_checking_response_handler)
        list(rdb_lib.acquire_hosts(self.host_scheduler, queue_entries))

        # Elevate the priority of the unimportant job, so we now have
        # 2 jobs at the same priority.
        self.db_helper.increment_priority(job_id=unimportant_job.id)
        queue_entries = self._dispatcher._refresh_pending_queue_entries()
        self._release_unused_hosts()
        list(rdb_lib.acquire_hosts(self.host_scheduler, queue_entries))

        # Prioritize the first job, and confirm that it gets the host over the
        # jobs that got it the last time.
        self.db_helper.increment_priority(job_id=unimportant_job.id)
        queue_entries = self._dispatcher._refresh_pending_queue_entries()
        self._release_unused_hosts()
        list(rdb_lib.acquire_hosts(self.host_scheduler, queue_entries))

