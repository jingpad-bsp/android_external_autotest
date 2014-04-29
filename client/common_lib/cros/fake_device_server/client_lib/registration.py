# Copyright 2014 The Chromium OS Authors. All rights reserved.
# Use of this source code is governed by a BSD-style license that can be
# found in the LICENSE file.

"""Module contains a simple client lib to the registration RPC."""

import json
import logging
import urllib2

import common
from fake_device_server.client_lib import common_client
from fake_device_server import registration_tickets


class RegistrationClient(common_client.CommonClient):
    """Client library for registrationTickets method."""

    def __init__(self, *args, **kwargs):
        common_client.CommonClient.__init__(
                self, registration_tickets.REGISTRATION_PATH, *args, **kwargs)


    def get_registration_ticket(self, ticket_id):
        """Returns info about the given |ticket_id|.

        @param ticket_id: valid id for a ticket.
        """
        url_h = urllib2.urlopen(self.get_url([ticket_id]))
        return json.loads(url_h.read())


    def update_registration_ticket(self, ticket_id, data,
                                   additional_headers=None, replace=False):
        """Updates the given registration ticket with the new data.

        @param ticket_id: id of the ticket to update.
        @param data: data to update.
        @param additional_headers: additional HTTP headers to pass (expects a
                list of tuples).
        @param replace: If True, replace all data with the given data using the
                PUT operation.
        """
        if not data:
            return

        headers = {'Content-Type': 'application/json'}
        if additional_headers:
            headers.update(additional_headers)

        request = urllib2.Request(self.get_url([ticket_id]), json.dumps(data),
                                  headers=headers)
        if replace:
            request.get_method = lambda: 'PUT'
        else:
            request.get_method = lambda: 'PATCH'

        url_h = urllib2.urlopen(request)
        return json.loads(url_h.read())


    def create_registration_ticket(self, initial_data=None):
        """Creates a new registration ticket.

        @param initial_data: optional dictionary of data to pass for ticket.
        """
        data = initial_data or {}
        request = urllib2.Request(self.get_url(), json.dumps(data),
                                  {'Content-Type': 'application/json'})
        url_h = urllib2.urlopen(request)
        return json.loads(url_h.read())


    def finalize_registration_ticket(self, ticket_id):
        """Finalizes a registration ticket by creating a new device.

        @param ticket_id: id of ticket to finalize.
        """
        request = urllib2.Request(self.get_url([ticket_id, 'finalize']),
                                  headers={'Content-Type': 'application/json'})
        request.get_method = lambda: 'POST'
        url_h = urllib2.urlopen(request)
        return json.loads(url_h.read())


    def register_device(self, system_name, device_kind, channel, **kwargs):
        """Goes through the entire registration process using the device args.

        @param system_name: name to give the system.
        @param device_kind: type of device.
        @param channel: supported communication channel.
        @param kwargs: additional dictionary of args to put in config.
        """
        ticket = self.create_registration_ticket()
        logging.info('Initial Ticket: %s', ticket)
        ticket_id = ticket['id']

        device_draft = dict(systemName=system_name,
                            deviceKind=device_kind,
                            channel=channel,
                            **kwargs)
        # Insert test auth.
        headers = [['Authorization',
                    'Bearer ' +
                    registration_tickets.RegistrationTickets.TEST_ACCESS_TOKEN]]

        ticket = self.update_registration_ticket(ticket_id,
                                                 {'deviceDraft': device_draft,
                                                  'userEmail': 'me'},
                                                 additional_headers=headers)

        logging.info('Updated Ticket After Claiming: %s', ticket)
        return self.finalize_registration_ticket(ticket_id)
