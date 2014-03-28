# Copyright 2014 The Chromium OS Authors. All rights reserved.
# Use of this source code is governed by a BSD-style license that can be
# found in the LICENSE file.

"""Module contains a simple implementation of the registrationTickets RPC."""

import json
import logging
import time
import uuid

import common
from cros_lib.fake_device_server import common_util
from cros_lib.fake_device_server import server_errors


class RegistrationTickets(object):
    """A simple implementation of the registrationTickets interface.

    A common workflow of using this API is:

    POST .../ # Creates a new ticket with <id>
    PATCH .../<id> with json blob # Updates ticket with device info.
    POST .../<id>/claim # Claims the device for a user.
    POST .../<id>/finalize # Finalize the device registration (robot info).

    We store the tickets based on a combination of <ticket_number> + <api_key>
    combo. The api_key can be passed in to any command with ?key=<api_key>.
    This isn't necessary though as using a default of None is ok.
    """
    # Constants for additional rest operations i.e.
    # .../<ticket_number>/claim | finalize
    FINALIZE = 'finalize'
    TEST_ACCESS_TOKEN = '1/TEST-ME'
    SUPPORTED_OPERATIONS = set([FINALIZE])

    # Needed for cherrypy to expose this to requests.
    exposed = True

    def __init__(self, registration_tickets):
        # Dictionary of tickets with keys of <id, api_key> pairs.
        self._tickets = registration_tickets


    def _common_parse(self, args_tuple, kwargs, operation_ok=False):
        """Common method to parse the args to this REST method.

        |args| contains all the sections of the URL after CherryPy removes the
        pieces that dispatched the URL to this handler. For instance,
        '.../<ticket number>/claim would manifest as:
        _common_parse('<ticket number>', 'claim').
        Some operations take no arguments: e.g., POST to this object creates a
        new registration ticket and takes no arguments). Other operations take
        a single argument (the ticket number): e.g., GET to this object
        returns a registration ticket resource. Still other operations take
        one of SUPPORTED_OPERATIONS as a second argument: e.g., POST with a
        ticket number and 'claim' should claim a ticket as belonging to a
        user.

        Args:
            args_tuple: Tuple of positional args.
            kwargs: Dictionary of named args passed in.
            operation_ok: If true, parse args[1] as an additional operation.

        Raises:
            server_error.HTTPError if combination or args/kwargs doesn't make
            sense.
        """
        args = list(args_tuple)
        api_key = kwargs.get('key')
        id = args.pop(0) if args else None
        operation = args.pop(0) if args else None
        if operation:
            if not operation_ok:
                raise server_errors.HTTPError(
                        400, 'Received operation when operation was not '
                        'expected: %s!' % operation)
            elif not operation in RegistrationTickets.SUPPORTED_OPERATIONS:
                raise server_errors.HTTPError(
                        400, 'Unsupported operation: %s' % operation)

        # All expected args should be popped off already.
        if args:
            raise server_errors.HTTPError(
                    400, 'Could not parse all args: %s' % args)

        return id, api_key, operation


    def _get_ticket(self, id, api_key):
        """Returns a ticket for the given id, api_key pair.

        Raises:
            server_errors.HTTPError if the ticket doesn't exist.
        """
        ticket = self._tickets.get((id, api_key))
        if ticket:
            return ticket
        else:
            raise server_errors.HTTPError(
                    400, 'Invalid registration ticket ID: %s' % id)


    def _finalize(self, id, api_key, ticket):
        """Finalizes the ticket by adding robot account info.

        Raises:
            server_errors.HTTPError if the ticket hasn't been claimed yet.
        """
        if 'userEmail' not in ticket:
            raise server_errors.HTTPError(400, 'Unclaimed ticket')

        robot_account_email = 'robot@test.org'
        robot_auth = uuid.uuid4().hex
        new_data = {'robotAccountEmail': robot_account_email,
                    'robotAccountAuthorizationCode':robot_auth}

        return self._update_ticket(id, api_key, new_data)


    def _add_claim_data(self, data):
        """Adds userEmail to |data| to claim ticket.

        Raises:
            server_errors.HTTPError if there is an authorization error.
        """
        access_token = common_util.grab_header_field('Authorization')
        if not access_token:
            raise server_errors.HTTPError(401, 'Missing Authorization.')

        # Authorization should contain "<type> <token>"
        access_token_list = access_token.split()
        if len(access_token_list) != 2:
            raise server_errors.HTTPError(400, 'Malformed Authorization field')

        [type, code] = access_token_list
        # TODO(sosa): Consider adding HTTP WWW-Authenticate response header
        # field
        if type != 'Bearer':
            raise server_errors.HTTPError(403, 'Authorization requires '
                                          'bearer token.')
        elif code != RegistrationTickets.TEST_ACCESS_TOKEN:
            raise server_errors.HTTPError(403, 'Wrong access token.')
        else:
            logging.info('Ticket is being claimed.')
            data['userEmail'] = 'test_account@chromium.org'


    def _update_ticket(self, id, api_key, data=None, update=True):
        """Helper method for all mutations to tickets.

        If the id isn't given, creates a new template ticket with a new id.
        Otherwise updates/replaces the given ticket with data based on update.

        Raises:
            server_errors.HTTPError if the ticket doesn't exist.
        """
        if not id:
            # Creating a new ticket.
            id = uuid.uuid4().hex
            current_time_ms = time.time() * 1000
            data = {'kind': 'clouddevices#registrationTicket',
                    'id': id,
                    'creationTimeMs': current_time_ms,
                    'expirationTimeMs': current_time_ms + (10 * 1000)}
            self._tickets[(id, api_key)] = data
            return data

        ticket = self._get_ticket(id, api_key)
        if not data:
            logging.warning('Received empty data update. Doing nothing.')
            return ticket

        # Handle claiming a ticket with an authorized request.
        if data.get('userEmail') == 'me':
            self._add_claim_data(data)

        # Update or replace the existing ticket.
        if update:
            ticket.update(data)
        else:
            if ticket.get('id') != data.get('id'):
                raise server_errors.HTTPError(400, "Ticket id doesn't match")

            ticket = data
            self._tickets[(id, api_key)] = data

        return ticket


    def GET(self, *args, **kwargs):
        """GET .../ticket_number returns info about the ticket.

        Raises:
            server_errors.HTTPError if the ticket doesn't exist.
        """
        id, api_key, _ = self._common_parse(args, kwargs)
        return json.dumps(self._get_ticket(id, api_key))


    def POST(self, *args, **kwargs):
        """Either creates a ticket OR claim/finalizes a ticket.

        This method implements the majority of the registration workflow.
        More specifically:
        POST ... creates a new ticket
        POST .../ticket_number/claim claims a given ticket with a fake email.
        POST .../ticket_number/finalize finalizes a ticket with a robot account.

        Raises:
            server_errors.HTTPError if the ticket should exist but doesn't
            (claim/finalize) or if we can't parse all the args.
        """
        id, api_key, operation = self._common_parse(args, kwargs,
                                                    operation_ok=True)
        if operation:
            ticket = self._get_ticket(id, api_key)
            if operation == RegistrationTickets.FINALIZE:
                return json.dumps(self._finalize(id, api_key, ticket))
            else:
                raise server_errors.HTTPError(
                        400, 'Unsupported method call %s' % operation)

        else:
            # We have an insert operation.
            data = common_util.parse_serialized_json()
            return json.dumps(self._update_ticket(id, api_key, data=data))


    def PATCH(self, *args, **kwargs):
        """Updates the given ticket with the incoming json blob.

        Format of this call is:
        PATCH .../ticket_number

        Caller must define a json blob to patch the ticket with.

        Raises:
            server_errors.HTTPError if the ticket doesn't exist.
        """
        id, api_key, _ = self._common_parse(args, kwargs)
        data = common_util.parse_serialized_json()
        return json.dumps(self._update_ticket(id, api_key, data=data))


    def PUT(self, *args, **kwargs):
        """Replaces the given ticket with the incoming json blob.

        Format of this call is:
        PUT .../ticket_number

        Caller must define a json blob to patch the ticket with.

        Raises:
            server_errors.HTTPError if the ticket doesn't exist.
        """
        id, api_key, _ = self._common_parse(args, kwargs)
        data = common_util.parse_serialized_json()
        return json.dumps(self._update_ticket(id, api_key, data=data,
                                              update=False))
