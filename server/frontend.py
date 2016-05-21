# Copyright Martin J. Bligh, Google Inc 2008
# Released under the GPL v2

"""
This class allows you to communicate with the frontend to submit jobs etc
It is designed for writing more sophisiticated server-side control files that
can recursively add and manage other jobs.

We turn the JSON dictionaries into real objects that are more idiomatic

For docs, see:
    http://www.chromium.org/chromium-os/testing/afe-rpc-infrastructure
    http://docs.djangoproject.com/en/dev/ref/models/querysets/#queryset-api
"""

#pylint: disable=missing-docstring

import getpass
import os
import re

import common
from autotest_lib.frontend.afe import rpc_client_lib
from autotest_lib.client.common_lib import control_data
from autotest_lib.client.common_lib import global_config
from autotest_lib.client.common_lib import utils
from autotest_lib.client.common_lib.cros.graphite import autotest_stats
from autotest_lib.tko import db


try:
    from autotest_lib.server.site_common import site_utils as server_utils
except:
    from autotest_lib.server import utils as server_utils
form_ntuples_from_machines = server_utils.form_ntuples_from_machines

GLOBAL_CONFIG = global_config.global_config
DEFAULT_SERVER = 'autotest'

_tko_timer = autotest_stats.Timer('tko')

def dump_object(header, obj):
    """
    Standard way to print out the frontend objects (eg job, host, acl, label)
    in a human-readable fashion for debugging
    """
    result = header + '\n'
    for key in obj.hash:
        if key == 'afe' or key == 'hash':
            continue
        result += '%20s: %s\n' % (key, obj.hash[key])
    return result


class RpcClient(object):
    """
    Abstract RPC class for communicating with the autotest frontend
    Inherited for both TKO and AFE uses.

    All the constructors go in the afe / tko class.
    Manipulating methods go in the object classes themselves
    """
    def __init__(self, path, user, server, print_log, debug, reply_debug):
        """
        Create a cached instance of a connection to the frontend

            user: username to connect as
            server: frontend server to connect to
            print_log: pring a logging message to stdout on every operation
            debug: print out all RPC traffic
        """
        if not user and utils.is_in_container():
            user = GLOBAL_CONFIG.get_config_value('SSP', 'user', default=None)
        if not user:
            user = getpass.getuser()
        if not server:
            if 'AUTOTEST_WEB' in os.environ:
                server = os.environ['AUTOTEST_WEB']
            else:
                server = GLOBAL_CONFIG.get_config_value('SERVER', 'hostname',
                                                        default=DEFAULT_SERVER)
        self.server = server
        self.user = user
        self.print_log = print_log
        self.debug = debug
        self.reply_debug = reply_debug
        headers = {'AUTHORIZATION': self.user}
        rpc_server = 'http://' + server + path
        if debug:
            print 'SERVER: %s' % rpc_server
            print 'HEADERS: %s' % headers
        self.proxy = rpc_client_lib.get_proxy(rpc_server, headers=headers)


    def run(self, call, **dargs):
        """
        Make a RPC call to the AFE server
        """
        rpc_call = getattr(self.proxy, call)
        if self.debug:
            print 'DEBUG: %s %s' % (call, dargs)
        try:
            result = utils.strip_unicode(rpc_call(**dargs))
            if self.reply_debug:
                print result
            return result
        except Exception:
            raise


    def log(self, message):
        if self.print_log:
            print message


class Planner(RpcClient):
    def __init__(self, user=None, server=None, print_log=True, debug=False,
                 reply_debug=False):
        super(Planner, self).__init__(path='/planner/server/rpc/',
                                      user=user,
                                      server=server,
                                      print_log=print_log,
                                      debug=debug,
                                      reply_debug=reply_debug)


class TKO(RpcClient):
    def __init__(self, user=None, server=None, print_log=True, debug=False,
                 reply_debug=False):
        super(TKO, self).__init__(path='/new_tko/server/noauth/rpc/',
                                  user=user,
                                  server=server,
                                  print_log=print_log,
                                  debug=debug,
                                  reply_debug=reply_debug)
        self._db = None


    @_tko_timer.decorate
    def get_job_test_statuses_from_db(self, job_id):
        """Get job test statuses from the database.

        Retrieve a set of fields from a job that reflect the status of each test
        run within a job.
        fields retrieved: status, test_name, reason, test_started_time,
                          test_finished_time, afe_job_id, job_owner, hostname.

        @param job_id: The afe job id to look up.
        @returns a TestStatus object of the resulting information.
        """
        if self._db is None:
            self._db = db.db()
        fields = ['status', 'test_name', 'subdir', 'reason',
                  'test_started_time', 'test_finished_time', 'afe_job_id',
                  'job_owner', 'hostname', 'job_tag']
        table = 'tko_test_view_2'
        where = 'job_tag like "%s-%%"' % job_id
        test_status = []
        # Run commit before we query to ensure that we are pulling the latest
        # results.
        self._db.commit()
        for entry in self._db.select(','.join(fields), table, (where, None)):
            status_dict = {}
            for key,value in zip(fields, entry):
                # All callers expect values to be a str object.
                status_dict[key] = str(value)
            # id is used by TestStatus to uniquely identify each Test Status
            # obj.
            status_dict['id'] = [status_dict['reason'], status_dict['hostname'],
                                 status_dict['test_name']]
            test_status.append(status_dict)

        return [TestStatus(self, e) for e in test_status]


    def get_status_counts(self, job, **data):
        entries = self.run('get_status_counts',
                           group_by=['hostname', 'test_name', 'reason'],
                           job_tag__startswith='%s-' % job, **data)
        return [TestStatus(self, e) for e in entries['groups']]


class AFE(RpcClient):
    def __init__(self, user=None, server=None, print_log=True, debug=False,
                 reply_debug=False, job=None):
        self.job = job
        super(AFE, self).__init__(path='/afe/server/noauth/rpc/',
                                  user=user,
                                  server=server,
                                  print_log=print_log,
                                  debug=debug,
                                  reply_debug=reply_debug)


    def host_statuses(self, live=None):
        dead_statuses = ['Repair Failed', 'Repairing']
        statuses = self.run('get_static_data')['host_statuses']
        if live == True:
            return list(set(statuses) - set(dead_statuses))
        if live == False:
            return dead_statuses
        else:
            return statuses


    @staticmethod
    def _dict_for_host_query(hostnames=(), status=None, label=None):
        query_args = {}
        if hostnames:
            query_args['hostname__in'] = hostnames
        if status:
            query_args['status'] = status
        if label:
            query_args['labels__name'] = label
        return query_args


    def get_hosts(self, hostnames=(), status=None, label=None, **dargs):
        query_args = dict(dargs)
        query_args.update(self._dict_for_host_query(hostnames=hostnames,
                                                    status=status,
                                                    label=label))
        hosts = self.run('get_hosts', **query_args)
        return [Host(self, h) for h in hosts]


    def get_hostnames(self, status=None, label=None, **dargs):
        """Like get_hosts() but returns hostnames instead of Host objects."""
        # This implementation can be replaced with a more efficient one
        # that does not query for entire host objects in the future.
        return [host_obj.hostname for host_obj in
                self.get_hosts(status=status, label=label, **dargs)]


    def reverify_hosts(self, hostnames=(), status=None, label=None):
        query_args = dict(locked=False,
                          aclgroup__users__login=self.user)
        query_args.update(self._dict_for_host_query(hostnames=hostnames,
                                                    status=status,
                                                    label=label))
        return self.run('reverify_hosts', **query_args)


    def create_host(self, hostname, **dargs):
        id = self.run('add_host', hostname=hostname, **dargs)
        return self.get_hosts(id=id)[0]


    def get_host_attribute(self, attr, **dargs):
        host_attrs = self.run('get_host_attribute', attribute=attr, **dargs)
        return [HostAttribute(self, a) for a in host_attrs]


    def set_host_attribute(self, attr, val, **dargs):
        self.run('set_host_attribute', attribute=attr, value=val, **dargs)


    def get_labels(self, **dargs):
        labels = self.run('get_labels', **dargs)
        return [Label(self, l) for l in labels]


    def create_label(self, name, **dargs):
        id = self.run('add_label', name=name, **dargs)
        return self.get_labels(id=id)[0]


    def get_acls(self, **dargs):
        acls = self.run('get_acl_groups', **dargs)
        return [Acl(self, a) for a in acls]


    def create_acl(self, name, **dargs):
        id = self.run('add_acl_group', name=name, **dargs)
        return self.get_acls(id=id)[0]


    def get_users(self, **dargs):
        users = self.run('get_users', **dargs)
        return [User(self, u) for u in users]


    def generate_control_file(self, tests, **dargs):
        ret = self.run('generate_control_file', tests=tests, **dargs)
        return ControlFile(self, ret)


    def get_jobs(self, summary=False, **dargs):
        if summary:
            jobs_data = self.run('get_jobs_summary', **dargs)
        else:
            jobs_data = self.run('get_jobs', **dargs)
        jobs = []
        for j in jobs_data:
            job = Job(self, j)
            # Set up some extra information defaults
            job.testname = re.sub('\s.*', '', job.name) # arbitrary default
            job.platform_results = {}
            job.platform_reasons = {}
            jobs.append(job)
        return jobs


    def get_host_queue_entries(self, **data):
        entries = self.run('get_host_queue_entries', **data)
        job_statuses = [JobStatus(self, e) for e in entries]

        # Sadly, get_host_queue_entries doesn't return platforms, we have
        # to get those back from an explicit get_hosts queury, then patch
        # the new host objects back into the host list.
        hostnames = [s.host.hostname for s in job_statuses if s.host]
        host_hash = {}
        for host in self.get_hosts(hostname__in=hostnames):
            host_hash[host.hostname] = host
        for status in job_statuses:
            if status.host:
                status.host = host_hash.get(status.host.hostname)
        # filter job statuses that have either host or meta_host
        return [status for status in job_statuses if (status.host or
                                                      status.meta_host)]


    def get_special_tasks(self, **data):
        tasks = self.run('get_special_tasks', **data)
        return [SpecialTask(self, t) for t in tasks]


    def get_host_special_tasks(self, host_id, **data):
        tasks = self.run('get_host_special_tasks',
                         host_id=host_id, **data)
        return [SpecialTask(self, t) for t in tasks]


    def get_host_status_task(self, host_id, end_time):
        task = self.run('get_host_status_task',
                        host_id=host_id, end_time=end_time)
        return SpecialTask(self, task) if task else None


    def get_host_diagnosis_interval(self, host_id, end_time, success):
        return self.run('get_host_diagnosis_interval',
                        host_id=host_id, end_time=end_time,
                        success=success)


    def create_job(self, control_file, name=' ', priority='Medium',
                control_type=control_data.CONTROL_TYPE_NAMES.CLIENT, **dargs):
        id = self.run('create_job', name=name, priority=priority,
                 control_file=control_file, control_type=control_type, **dargs)
        return self.get_jobs(id=id)[0]


    def abort_jobs(self, jobs):
        """Abort a list of jobs.

        Already completed jobs will not be affected.

        @param jobs: List of job ids to abort.
        """
        for job in jobs:
            self.run('abort_host_queue_entries', job_id=job)


class TestResults(object):
    """
    Container class used to hold the results of the tests for a job
    """
    def __init__(self):
        self.good = []
        self.fail = []
        self.pending = []


    def add(self, result):
        if result.complete_count > result.pass_count:
            self.fail.append(result)
        elif result.incomplete_count > 0:
            self.pending.append(result)
        else:
            self.good.append(result)


class RpcObject(object):
    """
    Generic object used to construct python objects from rpc calls
    """
    def __init__(self, afe, hash):
        self.afe = afe
        self.hash = hash
        self.__dict__.update(hash)


    def __str__(self):
        return dump_object(self.__repr__(), self)


class ControlFile(RpcObject):
    """
    AFE control file object

    Fields: synch_count, dependencies, control_file, is_server
    """
    def __repr__(self):
        return 'CONTROL FILE: %s' % self.control_file


class Label(RpcObject):
    """
    AFE label object

    Fields:
        name, invalid, platform, kernel_config, id, only_if_needed
    """
    def __repr__(self):
        return 'LABEL: %s' % self.name


    def add_hosts(self, hosts):
        return self.afe.run('label_add_hosts', id=self.id, hosts=hosts)


    def remove_hosts(self, hosts):
        return self.afe.run('label_remove_hosts', id=self.id, hosts=hosts)


class Acl(RpcObject):
    """
    AFE acl object

    Fields:
        users, hosts, description, name, id
    """
    def __repr__(self):
        return 'ACL: %s' % self.name


    def add_hosts(self, hosts):
        self.afe.log('Adding hosts %s to ACL %s' % (hosts, self.name))
        return self.afe.run('acl_group_add_hosts', self.id, hosts)


    def remove_hosts(self, hosts):
        self.afe.log('Removing hosts %s from ACL %s' % (hosts, self.name))
        return self.afe.run('acl_group_remove_hosts', self.id, hosts)


    def add_users(self, users):
        self.afe.log('Adding users %s to ACL %s' % (users, self.name))
        return self.afe.run('acl_group_add_users', id=self.name, users=users)


class Job(RpcObject):
    """
    AFE job object

    Fields:
        name, control_file, control_type, synch_count, reboot_before,
        run_verify, priority, email_list, created_on, dependencies,
        timeout, owner, reboot_after, id
    """
    def __repr__(self):
        return 'JOB: %s' % self.id


class JobStatus(RpcObject):
    """
    AFE job_status object

    Fields:
        status, complete, deleted, meta_host, host, active, execution_subdir, id
    """
    def __init__(self, afe, hash):
        super(JobStatus, self).__init__(afe, hash)
        self.job = Job(afe, self.job)
        if getattr(self, 'host'):
            self.host = Host(afe, self.host)


    def __repr__(self):
        if self.host and self.host.hostname:
            hostname = self.host.hostname
        else:
            hostname = 'None'
        return 'JOB STATUS: %s-%s' % (self.job.id, hostname)


class SpecialTask(RpcObject):
    """
    AFE special task object
    """
    def __init__(self, afe, hash):
        super(SpecialTask, self).__init__(afe, hash)
        self.host = Host(afe, self.host)


    def __repr__(self):
        return 'SPECIAL TASK: %s' % self.id


class Host(RpcObject):
    """
    AFE host object

    Fields:
        status, lock_time, locked_by, locked, hostname, invalid,
        synch_id, labels, platform, protection, dirty, id
    """
    def __repr__(self):
        return 'HOST OBJECT: %s' % self.hostname


    def show(self):
        labels = list(set(self.labels) - set([self.platform]))
        print '%-6s %-7s %-7s %-16s %s' % (self.hostname, self.status,
                                           self.locked, self.platform,
                                           ', '.join(labels))


    def delete(self):
        return self.afe.run('delete_host', id=self.id)


    def modify(self, **dargs):
        return self.afe.run('modify_host', id=self.id, **dargs)


    def get_acls(self):
        return self.afe.get_acls(hosts__hostname=self.hostname)


    def add_acl(self, acl_name):
        self.afe.log('Adding ACL %s to host %s' % (acl_name, self.hostname))
        return self.afe.run('acl_group_add_hosts', id=acl_name,
                            hosts=[self.hostname])


    def remove_acl(self, acl_name):
        self.afe.log('Removing ACL %s from host %s' % (acl_name, self.hostname))
        return self.afe.run('acl_group_remove_hosts', id=acl_name,
                            hosts=[self.hostname])


    def get_labels(self):
        return self.afe.get_labels(host__hostname__in=[self.hostname])


    def add_labels(self, labels):
        self.afe.log('Adding labels %s to host %s' % (labels, self.hostname))
        return self.afe.run('host_add_labels', id=self.id, labels=labels)


    def remove_labels(self, labels):
        self.afe.log('Removing labels %s from host %s' % (labels,self.hostname))
        return self.afe.run('host_remove_labels', id=self.id, labels=labels)


class User(RpcObject):
    def __repr__(self):
        return 'USER: %s' % self.login


class TestStatus(RpcObject):
    """
    TKO test status object

    Fields:
        test_idx, hostname, testname, id
        complete_count, incomplete_count, group_count, pass_count
    """
    def __repr__(self):
        return 'TEST STATUS: %s' % self.id


class HostAttribute(RpcObject):
    """
    AFE host attribute object

    Fields:
        id, host, attribute, value
    """
    def __repr__(self):
        return 'HOST ATTRIBUTE %d' % self.id
