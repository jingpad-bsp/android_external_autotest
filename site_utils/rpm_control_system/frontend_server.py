#!/usr/bin/python
# Copyright (c) 2012 The Chromium OS Authors. All rights reserved.
# Use of this source code is governed by a BSD-style license that can be
# found in the LICENSE file.

import errno
import heapq
import logging
import os
import re
import sys
import socket
import threading
import xmlrpclib

import rpm_logging_config
from config import rpm_config
from MultiThreadedXMLRPCServer import MultiThreadedXMLRPCServer
from rpm_infrastructure_exception import RPMInfrastructureException

import common
from autotest_lib.site_utils.rpm_control_system import utils

DEFAULT_RPM_COUNT = 0
TERMINATED = -1

# Indexes for accessing heap entries.
RPM_COUNT = 0
DISPATCHER_URI = 1

LOG_FILENAME_FORMAT = rpm_config.get('GENERAL','frontend_logname_format')
DEFAULT_RPM_ID = rpm_config.get('RPM_INFRASTRUCTURE', 'default_rpm_id')

# Valid state values.
VALID_STATE_VALUES = ['ON', 'OFF', 'CYCLE']

# RPM Hostname regex.
RPM_REGEX = re.compile('host[^.]*')

# Servo-interface mapping file
MAPPING_FILE = os.path.join(
        os.path.dirname(__file__),
        rpm_config.get('CiscoPOE', 'servo_interface_mapping_file'))


class RPMFrontendServer(object):
    """
    This class is the frontend server of the RPM Infrastructure. All clients
    will send their DUT power state requests to this central server who will
    forward the requests to an avaliable or already assigned RPM dispatcher
    server.

    Once the dispatcher processes the request it will return the result
    to this frontend server who will send the result back to the client.

    All calls to this server are blocking.

    @var _dispatcher_minheap: Min heap that returns a list of format-
                              [ num_rpm's, dispatcher_uri ]
                              Used to choose the least loaded dispatcher.
    @var _entry_dict: Maps dispatcher URI to an entry (list) inside the min
                     heap. If a dispatcher server shuts down this allows us to
                     invalidate the entry in the minheap.
    @var _lock: Used to protect data from multiple running threads all
                manipulating the same data.
    @var _rpm_dict: Maps rpm hostname's to an already assigned dispatcher
                    server.
    @var _mapping_last_modified: Last-modified time of the servo-interface
                                 mapping file.
    @var _servo_interface: Maps servo hostname to (switch_hostname, interface).
    @var _email_handler: Email handler to use to control email notifications.
    """


    def __init__(self, email_handler=None):
        """
        RPMFrontendServer constructor.

        Initializes instance variables.
        """
        self._dispatcher_minheap = []
        self._entry_dict = {}
        self._lock = threading.Lock()
        self._rpm_dict = {}
        self._mapping_last_modified = os.path.getmtime(MAPPING_FILE)
        self._servo_interface = utils.load_servo_interface_mapping()
        self._email_handler = email_handler


    def queue_request(self, dut_hostname, new_state):
        """
        Forwards a request to change a DUT's power state to the appropriate
        dispatcher server.

        This call will block until the forwarded request returns.

        @param dut_hostname: Hostname of the DUT whose power state we want to
                             change.
        @param new_state: [ON, OFF, CYCLE] State to which we want to set the
                          DUT's outlet to.

        @return: True if the attempt to change power state was successful,
                 False otherwise.

        @raise RPMInfrastructureException: No dispatchers are available or can
                                           be reached.
        """
        # Remove any DNS Zone information and simplify down to just the dut
        # hostname.
        dut_hostname = dut_hostname.split('.')[0]
        new_state = new_state.upper()
        # Put new_state in all uppercase letters
        if new_state not in VALID_STATE_VALUES:
            logging.error('Received request to set DUT: %s to invalid state %s',
                          dut_hostname, new_state)
            return False
        logging.info('Received request to set DUT: %s to state: %s',
                     dut_hostname, new_state)
        dispatcher_uri = self._get_dispatcher(dut_hostname)
        if not dispatcher_uri:
            # No dispatchers available.
            raise RPMInfrastructureException('No dispatchers available.')
        client = xmlrpclib.ServerProxy(dispatcher_uri)
        try:
            # Block on the request and return the result once it arrives.
            return client.queue_request(dut_hostname, new_state)
        except socket.error as er:
            # Dispatcher Server is not reachable. Unregister it and retry.
            logging.error("Can't reach Dispatch Server: %s. Error: %s",
                          dispatcher_uri, errno.errorcode[er.errno])
            if self.is_network_infrastructure_down():
                # No dispatchers can handle this request so raise an Exception
                # to the caller.
                raise RPMInfrastructureException('No dispatchers can be'
                                                 'reached.')
            logging.info('Will attempt forwarding request to other dispatch '
                         'servers.')
            logging.error('Unregistering %s due to error. Recommend resetting '
                          'that dispatch server.', dispatcher_uri)
            self.unregister_dispatcher(dispatcher_uri)
            # Retry forwarding the request.
            return self.queue_request(dut_hostname, new_state)


    def is_network_infrastructure_down(self):
        """
        Check to see if we can communicate with any dispatcher servers.

        Only called in the situation that queuing a request to a dispatcher
        server failed.

        @return: False if any dispatcher server is up and the rpm infrastructure
                 can still function. True otherwise.
        """
        for dispatcher_entry in self._dispatcher_minheap:
            dispatcher = xmlrpclib.ServerProxy(dispatcher_entry[DISPATCHER_URI])
            try:
                if dispatcher.is_up():
                    # Atleast one dispatcher is alive so our network is fine.
                    return False
            except socket.error:
                # Can't talk to this dispatcher so keep looping.
                pass
        logging.error("Can't reach any dispatchers. Check frontend network "
                      'status or all dispatchers are down.')
        return True


    def _get_dispatcher(self, dut_hostname):
        """
        Private method that looks up or assigns a dispatcher server
        responsible for communicating with the given DUT's RPM.

        Will also call _check_dispatcher to make sure it is up before returning
        it.

        @param dut_hostname: Hostname of the DUT whose dispatcher URI we want
                             to retrieve.

        @return: URI of dispatcher server responsible for this DUT's rpm. None
                 if no dispatcher servers are available.
        """
        if dut_hostname.endswith('servo'):
            # Servos are managed by Cisco POE switches.
            reload_info = utils.reload_servo_interface_mapping_if_necessary(
                    self._mapping_last_modified)
            if reload_info:
                self._mapping_last_modified, self._servo_interface = reload_info
            switch_if_tuple = self._servo_interface.get(dut_hostname)
            if not switch_if_tuple:
                logging.error('Could not determine POE hostname for %s. '
                              'Please check the servo-interface mapping file.',
                              dut_hostname)
                return None
            else:
                rpm_hostname = switch_if_tuple[0]
        else:
            # Regular DUTs are managed by RPMs.
            rpm_hostname = RPM_REGEX.sub(DEFAULT_RPM_ID, dut_hostname, count=1)
        with self._lock:
            if self._rpm_dict.get(rpm_hostname):
                return self._rpm_dict[rpm_hostname]
            logging.info('No Dispatcher assigned for RPM %s.', rpm_hostname)
            # Choose the least loaded dispatcher to communicate with the RPM.
            try:
                heap_entry = heapq.heappop(self._dispatcher_minheap)
            except IndexError:
                logging.error('Infrastructure Error: Frontend has no'
                              'registered dispatchers to field out this '
                              'request!')
                return None
            dispatcher_uri = heap_entry[DISPATCHER_URI]
            # Put this entry back in the heap with an RPM Count + 1.
            heap_entry[RPM_COUNT] = heap_entry[RPM_COUNT] + 1
            heapq.heappush(self._dispatcher_minheap, heap_entry)
            logging.info('Assigning %s for RPM %s', dispatcher_uri,
                         rpm_hostname)
            self._rpm_dict[rpm_hostname] = dispatcher_uri
            return dispatcher_uri


    def register_dispatcher(self, dispatcher_uri):
        """
        Called by a dispatcher server so that the frontend server knows it is
        available to field out RPM requests.

        Adds an entry to the min heap and entry map for this dispatcher.

        @param dispatcher_uri: Address of dispatcher server we are registering.
        """
        logging.info('Registering uri: %s as a rpm dispatcher.', dispatcher_uri)
        with self._lock:
            heap_entry = [DEFAULT_RPM_COUNT, dispatcher_uri]
            heapq.heappush(self._dispatcher_minheap, heap_entry)
            self._entry_dict[dispatcher_uri] = heap_entry


    def unregister_dispatcher(self, uri_to_unregister):
        """
        Called by a dispatcher server as it exits so that the frontend server
        knows that it is no longer available to field out requests.

        Assigns an rpm count of -1 to this dispatcher so that it will be pushed
        out of the min heap.

        Removes from _rpm_dict all entries with the value of this dispatcher so
        that those RPM's can be reassigned to a new dispatcher.

        @param uri_to_unregister: Address of dispatcher server we are
                                  unregistering.
        """
        logging.info('Unregistering uri: %s as a rpm dispatcher.',
                     uri_to_unregister)
        with self._lock:
            heap_entry = self._entry_dict.get(uri_to_unregister)
            if not heap_entry:
                logging.warning('%s was not registered.', uri_to_unregister)
                return
            # Set this entry's RPM_COUNT to TERMINATED (-1).
            heap_entry[RPM_COUNT] = TERMINATED
            # Remove all RPM mappings.
            for rpm, dispatcher in self._rpm_dict.items():
                if dispatcher == uri_to_unregister:
                    self._rpm_dict[rpm] = None
            self._entry_dict[uri_to_unregister] = None
            # Re-sort the heap and remove any terminated dispatchers.
            heapq.heapify(self._dispatcher_minheap)
            self._remove_terminated_dispatchers()


    def _remove_terminated_dispatchers(self):
        """
        Peek at the head of the heap and keep popping off values until there is
        a non-terminated dispatcher at the top.
        """
        # Heapq guarantees the head of the heap is in the '0' index.
        try:
            # Peek at the next element in the heap.
            top_of_heap = self._dispatcher_minheap[0]
            while top_of_heap[RPM_COUNT] is TERMINATED:
                # Pop off the top element.
                heapq.heappop(self._dispatcher_minheap)
                # Peek at the next element in the heap.
                top_of_heap = self._dispatcher_minheap[0]
        except IndexError:
            # No more values in the heap. Can be thrown by both minheap[0]
            # statements.
            pass


    def suspend_emails(self, hours):
        """Suspend email notifications.

        @param hours: How many hours to suspend email notifications.
        """
        if self._email_handler:
            self._email_handler.suspend_emails(hours)


    def resume_emails(self):
        """Resume email notifications."""
        if self._email_handler:
            self._email_handler.resume_emails()


if __name__ == '__main__':
    """
    Main function used to launch the frontend server. Creates an instance of
    RPMFrontendServer and registers it to a MultiThreadedXMLRPCServer instance.
    """
    if len(sys.argv) > 1:
      print 'Usage: ./%s, no arguments available.' % sys.argv[0]
      sys.exit(1)
    email_handler = rpm_logging_config.set_up_logging(LOG_FILENAME_FORMAT)
    frontend_server = RPMFrontendServer(email_handler=email_handler)
    address = rpm_config.get('RPM_INFRASTRUCTURE', 'frontend_addr')
    port = rpm_config.getint('RPM_INFRASTRUCTURE', 'frontend_port')
    server = MultiThreadedXMLRPCServer((address, port), allow_none=True)
    server.register_instance(frontend_server)
    logging.info('Listening on %s port %d', address, port)
    server.serve_forever()
