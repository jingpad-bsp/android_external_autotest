"""Rdb server module.
"""

import collections
import logging

import common

from django.core import exceptions as django_exceptions
from django.db.models import fields
from django.db.models import Q
from autotest_lib.frontend.afe import models
from autotest_lib.scheduler import rdb_utils
from autotest_lib.site_utils.graphite import stats


_timer = stats.Timer('rdb')


# Qeury managers: Provide a layer of abstraction over the database by
# encapsulating common query patterns used by the rdb.
class BaseHostQueryManager(object):
    """Base manager for host queries on all hosts.
    """

    host_objects = models.Host.objects


    def update_hosts(self, host_ids, **kwargs):
        """Update fields on a hosts.

        @param host_ids: A list of ids of hosts to update.
        @param kwargs: A key value dictionary corresponding to column, value
            in the host database.
        """
        self.host_objects.filter(id__in=host_ids).update(**kwargs)


    @rdb_utils.return_rdb_host
    def get_hosts(self, ids):
        """Get host objects for the given ids.

        @param ids: The ids for which we need host objects.

        @returns: A list of RDBServerHostWrapper objects, ordered by host_id.
        """
        return self.host_objects.filter(id__in=ids).order_by('id')


    @rdb_utils.return_rdb_host
    def find_hosts(self, deps, acls):
        """Finds valid hosts matching deps, acls.

        @param deps: A list of dependencies to match.
        @param acls: A list of acls, at least one of which must coincide with
            an acl group the chosen host is in.

        @return: A list of matching hosts available.
        """
        hosts_available = self.host_objects.filter(invalid=0)
        queries = [Q(labels__id=dep) for dep in deps]
        queries += [Q(aclgroup__id__in=acls)]
        for query in queries:
            hosts_available = hosts_available.filter(query)
        return hosts_available


class AvailableHostQueryManager(BaseHostQueryManager):
    """Query manager for requests on un-leased, un-locked hosts.
    """

    host_objects = models.Host.leased_objects


# Request Handlers: Used in conjunction with requests in rdb_utils, these
# handlers acquire hosts for a request and record the acquisition in
# an response_map dictionary keyed on the request itself, with the host/hosts
# as values.
class BaseHostRequestHandler(object):
    """Handler for requests related to hosts, leased or unleased.

    This class is only capable of blindly returning host information.
    """

    def __init__(self):
        self.host_query_manager = BaseHostQueryManager()
        self.response_map = {}


    def update_response_map(self, request, response):
        """Record a response for a request.

        The response_map only contains requests that were either satisfied, or
        that ran into an exception. Often this translates to reserving hosts
        against a request. If the rdb hit an exception processing a request, the
        exception gets recorded in the map for the client to reraise.

        @param response: A response for the request.
        @param request: The request that has reserved these hosts.

        @raises RDBException: If an empty values is added to the map.
        """
        if not response:
            raise rdb_utils.RDBException('response_map dict can only contain '
                    'valid responses. Request %s, response %s is invalid.' %
                     (request, response))
        if self.response_map.get(request):
            raise rdb_utils.RDBException('Request %s already has response %s '
                                         'the rdb cannot return multiple '
                                         'responses for the same request.' %
                                         (request, response))
        self.response_map[request] = response


    def _record_exceptions(self, request, exceptions):
        """Record a list of exceptions for a request.

        @param request: The request for which the exceptions were hit.
        @param exceptions: The exceptions hit while processing the request.
        """
        rdb_exceptions = [rdb_utils.RDBException(ex) for ex in exceptions]
        self.update_response_map(request, rdb_exceptions)


    def get_response(self):
        """Convert all RDBServerHostWrapper objects to host info dictionaries.

        @return: A dictionary mapping requests to a list of matching host_infos.
        """
        for request, response in self.response_map.iteritems():
            self.response_map[request] = [reply.wire_format()
                                          for reply in response]
        return self.response_map


    def update_hosts(self, update_requests):
        """Updates host tables with a payload.

        @param update_requests: A list of update requests, as defined in
            rdb_utils.UpdateHostRequest.
        """
        # Last payload for a host_id wins in the case of conflicting requests.
        unique_host_requests = {}
        for request in update_requests:
            if unique_host_requests.get(request.host_id):
                unique_host_requests[request.host_id].update(request.payload)
            else:
                unique_host_requests[request.host_id] = request.payload

        # Batch similar payloads so we can do them in one table scan.
        similar_requests = {}
        for host_id, payload in unique_host_requests.iteritems():
            similar_requests.setdefault(payload, []).append(host_id)

        # If fields of the update don't match columns in the database,
        # record the exception in the response map. This also means later
        # updates will get applied even if previous updates fail.
        for payload, hosts in similar_requests.iteritems():
            try:
                response = self.host_query_manager.update_hosts(hosts, **payload)
            except (django_exceptions.FieldError,
                    fields.FieldDoesNotExist) as e:
                for host in hosts:
                    # Since update requests have a consistent hash this will map
                    # to the same key as the original request.
                    request = rdb_utils.UpdateHostRequest(
                            host_id=host, payload=payload).get_request()
                    self._record_exceptions(request, [e])


    def batch_get_hosts(self, host_requests):
        """Get hosts matching the requests.

        This method does not acquire the hosts, i.e it reserves hosts against
        requests leaving their leased state untouched.

        @param host_requests: A list of requests, as defined in
            rdb_utils.BaseHostRequest.
        """
        host_ids = set([request.host_id for request in host_requests])
        host_map = {}

        # This list will not contain available hosts if executed using
        # an AvailableHostQueryManager.
        for host in self.host_query_manager.get_hosts(host_ids):
            host_map[host.id] = host
        for request in host_requests:
            if request.host_id in host_map:
                self.update_response_map(request, [host_map[request.host_id]])
            else:
                logging.warning('rdb could not get host for request: %s, it '
                                'is already leased or locked', request)


class AvailableHostRequestHandler(BaseHostRequestHandler):
    """Handler for requests related to available (unleased and unlocked) hosts.

    This class is capable of acquiring or validating hosts for requests.
    """


    def __init__(self):
        self.host_query_manager = AvailableHostQueryManager()
        self.response_map = {}


    def lease_hosts(self, hosts):
        """Leases a list hosts.

        @param hosts: A list of hosts to lease.
        """
        requests = [rdb_utils.UpdateHostRequest(host_id=host.id,
                payload={'leased': 1}).get_request() for host in hosts]
        super(AvailableHostRequestHandler, self).update_hosts(requests)


    @_timer.decorate
    def batch_acquire_hosts(self, host_requests):
        """Acquire hosts for a list of requests.

        The act of acquisition involves finding and leasing a set of
        hosts that match the parameters of a request. Each acquired
        host is added to the response_map dictionary, as an
        RDBServerHostWrapper.

        @param host_requests: A list of requests to acquire hosts.
        """
        # Group similar requests and sort by priority, so we don't invert
        # priorities and lease hosts based on demand alone.
        batched_host_request = sorted(
                collections.Counter(host_requests).items(),
                key=lambda request: request[0].priority, reverse=True)

        for request, count in batched_host_request:
            hosts = self.host_query_manager.find_hosts(
                            request.deps, request.acls)
            num_hosts = min(len(hosts), count)
            if num_hosts:
                # TODO(beeps): Only reserve hosts we have successfully leased.
                self.lease_hosts(hosts[:num_hosts])
                self.update_response_map(request, hosts[:num_hosts])
            if num_hosts < count:
                logging.warning('%s Unsatisfied rdb acquisition request:%s ',
                                count-num_hosts, request)


    @_timer.decorate
    def batch_validate_hosts(self, requests):
        """Validate requests with hosts.

        Reserve all hosts, check each one for validity and discard invalid
        request-host pairings. Lease the remaining hsots.

        @param requests: A list of requests to validate.
        """
        # Multiple requests can have the same host (but different acls/deps),
        # and multiple jobs can submit identical requests (same host_id,
        # acls, deps). In both these cases the first request to check the host
        # map wins, though in the second case it doesn't matter.
        self.batch_get_hosts(set(requests))
        for request in self.response_map.keys():
            hosts = self.response_map[request]
            if len(hosts) > 1:
                raise rdb_utils.RDBException('Got multiple hosts for a single '
                        'request. Hosts: %s, request %s.' % (hosts, request))
            host = hosts[0]
            if not ((request.acls.intersection(host.acls) or host.invalid) and
                    request.deps.intersection(host.labels) == request.deps):
                if request.host_id != host.id:
                    raise rdb_utils.RDBException('Cannot assign a different '
                            'host for requset: %s, it already has one: %s ' %
                            (request, host.id))
                del self.response_map[request]
                logging.warning('Failed rdb validation request:%s ', request)

        # TODO(beeps): Update acquired hosts with failed leases.
        self.lease_hosts([hosts[0] for hosts in self.response_map.values()])


# Request dispatchers: Create the appropriate request handler, send a list
# of requests to one of its methods. The corresponding request handler in
# rdb_lib must understand how to match each request with a response from a
# dispatcher, the easiest way to achieve this is to returned the response_map
# attribute of the request handler, after making the appropriate requests.
def get_hosts(host_requests):
    """Get host information about the requested hosts.

    @param host_requests: A list of requests as defined in BaseHostRequest.
    @return: A dictionary mapping each request to a list of hosts.
    """
    rdb_handler = BaseHostRequestHandler()
    rdb_handler.batch_get_hosts(host_requests)
    return rdb_handler.get_response()


def update_hosts(update_requests):
    """Update hosts.

    @param update_requests: A list of updates to host tables
        as defined in UpdateHostRequest.
    """
    rdb_handler = BaseHostRequestHandler()
    rdb_handler.update_hosts(update_requests)
    return rdb_handler.get_response()


def rdb_host_request_dispatcher(host_requests):
    """Dispatcher for all host acquisition queries.

    @param host_requests: A list of requests for acquiring hosts, as defined in
        AcquireHostRequest.
    @return: A dictionary mapping each request to a list of hosts, or
        an empty list if none could satisfy the request. Eg:
        {AcquireHostRequest.template: [host_info_dictionaries]}
    """
    validation_requests = []
    require_hosts_requests = []

    # Validation requests are made by a job scheduled against a specific host
    # specific host (eg: through the frontend) and only require the rdb to
    # match the parameters of the host against the request. Acquisition
    # requests are made by jobs that need hosts (eg: suites) and the rdb needs
    # to find hosts matching the parameters of the request.
    for request in host_requests:
        if request.host_id:
            validation_requests.append(request)
        else:
            require_hosts_requests.append(request)

    rdb_handler = AvailableHostRequestHandler()
    rdb_handler.batch_validate_hosts(validation_requests)
    rdb_handler.batch_acquire_hosts(require_hosts_requests)
    return rdb_handler.get_response()
