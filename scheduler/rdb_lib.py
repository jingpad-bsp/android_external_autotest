"""Performs translation between monitor_db and the rdb.
"""
import logging

import common
from autotest_lib.scheduler import rdb
from autotest_lib.scheduler import rdb_utils
from autotest_lib.server.cros import provision


# RDB request managers: Call an rdb api_method with a list of RDBRequests, and
# match the requests to the responses returned.
class RDBRequestManager(object):
    """Base request manager for RDB requests.

    Each instance of a request manager is associated with one request, and
    one api call. All subclasses maintain a queue of unexecuted requests, and
    and expose an api to add requests/retrieve the response for these requests.
    """


    def __init__(self, request, api_call):
        """
        @param request: A subclass of rdb_utls.RDBRequest. The manager can only
            manage requests of one type.
        @param api_call: The rdb api call this manager is expected to make.
            A manager can only send requests of type request, to this api call.
        """
        self.request = request
        self.api_call = api_call
        self.request_queue = []


    def add_request(self, **kwargs):
        """Add an RDBRequest to the queue."""
        self.request_queue.append(self.request(**kwargs).get_request())


    def response(self):
        """Execute the api call and return a response for each request.

        The order of responses is the same as the order of requests added
        to the queue.

        @yield: A response for each request added to the queue after the
            last invocation of response.
        """
        if not self.request_queue:
            raise rdb_utils.RDBException('No requests. Call add_requests '
                    'with the appropriate kwargs, before calling response.')

        result = self.api_call(self.request_queue)
        requests = self.request_queue
        self.request_queue = []
        for request in requests:
            yield result.get(request) if result else None


class BaseHostRequestManager(RDBRequestManager):
    """Manager for batched get requests on hosts."""


    def response(self):
        """Yields a popped host from the returned host list."""

        # As a side-effect of returning a host, this method also removes it
        # from the list of hosts matched up against a request. Eg:
        #    hqes: [hqe1, hqe2, hqe3]
        #    client requests: [c_r1, c_r2, c_r3]
        #    generate requests in rdb: [r1 (c_r1 and c_r2), r2]
        #    and response {r1: [h1, h2], r2:[h3]}
        # c_r1 and c_r2 need to get different hosts though they're the same
        # request, because they're from different queue_entries.
        for hosts in super(BaseHostRequestManager, self).response():
            yield hosts.pop() if hosts else None


# Scheduler host proxy: Convert host information returned by the rdb into
# a client host object capable of proxying updates back to the rdb.
class RDBClientHostWrapper(object):
    """A wrapper for host information.

    This wrapper is used whenever the queue entry needs direct access
    to the host.
    """

    required_fields = set(['id', 'hostname', 'platform','labels',
                           'acls', 'protection', 'dirty', 'status'])


    def _update_attributes(self, new_attributes):
        """Updates attributes based on an input dictionary.

        Since reads are not proxied to the rdb this method caches updates to
        the host tables as class attributes.

        @param new_attributes: A dictionary of attributes to update.
        """
        for name, value in new_attributes.iteritems():
            setattr(self, name, value)


    def __init__(self, **kwargs):
        if self.required_fields - set(kwargs.keys()):
            raise rdb_utils.RDBException('Creating %s requires %s, got %s '
                    % (self.__class__, self.required_fields, kwargs.keys()))
        self._update_attributes(kwargs)
        self.update_request_manager = RDBRequestManager(
                rdb_utils.UpdateHostRequest, rdb.update_hosts)
        self.dbg_str = ''


    def _update(self, payload):
        """Send an update to rdb, save the attributes of the payload locally.

        @param: A dictionary representing 'key':value of the update required.

        @raises RDBException: If the update fails.
        """
        logging.info('Host %s in %s updating %s through rdb on behalf of: %s ',
                     self.hostname, self.status, payload, self.dbg_str)
        self.update_request_manager.add_request(host_id=self.id, payload=payload)
        for response in self.update_request_manager.response():
            if response:
                raise rdb_utils.RDBException('Host %s unable to perform update '
                        '%s through rdb on behalf of %s: %s',  self.hostname,
                        payload, self.dbg_str, response)
        self._update_attributes(payload)


    def set_status(self, status):
        """Proxy for setting the status of a host via the rdb.

        @param status: The new status.
        """
        self._update({'status': status})


    def update_field(self, fieldname, value):
        """Proxy for updating a field on the host.

        @param fieldname: The fieldname as a string.
        @param value: The value to assign to the field.
        """
        self._update({fieldname: value})


    def platform_and_labels(self):
        """Get the platform and labels on this host.

        @return: A tuple containing a list of label names, and the platform name.
        """
        platform = self.platform
        labels = [label for label in self.labels if label != platform]
        return platform, labels


# Adapters for scheduler specific objects: Convert job information to a
# format more ameanable to the rdb/rdb request managers.
class JobQueryManager(object):
    """A caching query manager for all job related information."""
    def __init__(self, host_scheduler, queue_entries):

        # TODO(beeps): Break the dependency on the host_scheduler,
        # crbug.com/336934.
        self.host_scheduler = host_scheduler
        jobs = [queue_entry.job_id for queue_entry in queue_entries]
        self._job_acls = self.host_scheduler._get_job_acl_groups(jobs)
        self._job_deps = self.host_scheduler._get_job_dependencies(jobs)
        self._labels = self.host_scheduler._get_labels(self._job_deps)


    def get_job_info(self, queue_entry):
        """Extract job information from a queue_entry/host-scheduler.

        @param queue_entry: The queue_entry for which we need job information.

        @return: A dictionary representing job related information.
        """
        job_id = queue_entry.job_id
        job_deps = self._job_deps.get(job_id, [])
        job_deps = [dep for dep in job_deps
                    if not provision.can_provision(self._labels[dep].name)]
        job_acls = self._job_acls.get(job_id, [])

        return {'deps': job_deps, 'acls': job_acls,
                'host_id': queue_entry.host_id}


def acquire_hosts(host_scheduler, queue_entries):
    """Acquire hosts for the list of queue_entries.

    @param queue_entries: A list of queue_entries that need hosts.
    @param host_scheduler: The host_scheduler object, needed to get job
        information.

    @yield: An RDBClientHostWrapper for each host acquired on behalf of a
        queue_entry, or None if a host wasn't found.

    @raises RDBException: If something goes wrong making the request.
    """
    job_query_manager = JobQueryManager(host_scheduler, queue_entries)
    request_manager = BaseHostRequestManager(
            rdb_utils.AcquireHostRequest, rdb.rdb_host_request_dispatcher)
    for entry in queue_entries:
        request_manager.add_request(**job_query_manager.get_job_info(entry))

    for host in request_manager.response():
        yield (RDBClientHostWrapper(**host)
               if host else None)


def get_hosts(host_ids):
    """Get information about the hosts with ids in host_ids.

    @param host_ids: A list of host_ids.

    @return: A list of RDBClientHostWrapper objects.

    @raises RDBException: If something goes wrong in making the request.
    """
    request_manager = BaseHostRequestManager(rdb_utils.HostRequest, rdb.get_hosts)
    for host_id in host_ids:
        request_manager.add_request(host_id=host_id)

    hosts = []
    for host in request_manager.response():
        hosts.append(RDBClientHostWrapper(**host)
                     if host else None)
    return hosts
