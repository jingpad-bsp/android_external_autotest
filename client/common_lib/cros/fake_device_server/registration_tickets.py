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
    """
    # OAUTH2 Bearer Access Token
    TEST_ACCESS_TOKEN = '1/TEST-ME'

    # Needed for cherrypy to expose this to requests.
    exposed = True


    def __init__(self, resource):
        """Initializes a registration ticket.

        @param resource: A resource delegate.
        """
        self.resource = resource


    def _default_registration_ticket(self):
        """Creates and returns a new registration ticket."""
        current_time_ms = time.time() * 1000
        ticket = {'kind': 'clouddevices#registrationTicket',
                  'creationTimeMs': current_time_ms,
                  'expirationTimeMs': current_time_ms + (10 * 1000)}
        return ticket


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
        return self.resource.update_data_val(id, api_key, new_data)


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


    def GET(self, *args, **kwargs):
        """GET .../ticket_number returns info about the ticket.

        Raises:
            server_errors.HTTPError if the ticket doesn't exist.
        """
        id, api_key, _ = common_util.parse_common_args(args, kwargs)
        return json.dumps(self.resource.get_data_val(id, api_key))


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
        id, api_key, operation = common_util.parse_common_args(
                args, kwargs, supported_operations=set(['finalize']))
        if operation:
            ticket = self.resource.get_data_val(id, api_key)
            if operation == 'finalize':
                return json.dumps(self._finalize(id, api_key, ticket))
            else:
                raise server_errors.HTTPError(
                        400, 'Unsupported method call %s' % operation)

        else:
            data = common_util.parse_serialized_json()
            if not data:
                data = {}

            # We have an insert operation so make sure we have all required
            # fields.
            if not id:
                data.update(self._default_registration_ticket())

            return json.dumps(self.resource.update_data_val(
                    id, api_key, data_in=data))


    def PATCH(self, *args, **kwargs):
        """Updates the given ticket with the incoming json blob.

        Format of this call is:
        PATCH .../ticket_number

        Caller must define a json blob to patch the ticket with.

        Raises:
            server_errors.HTTPError if the ticket doesn't exist.
        """
        id, api_key, _ = common_util.parse_common_args(args, kwargs)
        data = common_util.parse_serialized_json()

        # Handle claiming a ticket with an authorized request.
        if data and data.get('userEmail') == 'me':
            self._add_claim_data(data)

        return json.dumps(self.resource.update_data_val(
                id, api_key, data_in=data))


    def PUT(self, *args, **kwargs):
        """Replaces the given ticket with the incoming json blob.

        Format of this call is:
        PUT .../ticket_number

        Caller must define a json blob to patch the ticket with.

        Raises:
        """
        id, api_key, _ = common_util.parse_common_args(args, kwargs)
        data = common_util.parse_serialized_json()

        # Handle claiming a ticket with an authorized request.
        if data and data.get('userEmail') == 'me':
            self._add_claim_data(data)

        return json.dumps(self.resource.update_data_val(
                id, api_key, data_in=data, update=False))
