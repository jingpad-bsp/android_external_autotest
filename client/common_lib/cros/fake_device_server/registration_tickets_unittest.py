#! /usr/bin/python

# Copyright 2014 The Chromium OS Authors. All rights reserved.
# Use of this source code is governed by a BSD-style license that can be
# found in the LICENSE file.

"""Unit tests for registration_tickets.py."""

import json
import mox
import unittest

import common
from cros_lib.fake_device_server import common_util
from cros_lib.fake_device_server import registration_tickets
from cros_lib.fake_device_server import server_errors


class RegistrationTicketsTest(mox.MoxTestBase):
    """Tests for the RegistrationTickets class."""

    def setUp(self):
        """Sets up mox and a ticket / registration objects."""
        mox.MoxTestBase.setUp(self)
        self.tickets = {}
        self.registration = registration_tickets.RegistrationTickets(
                self.tickets)


    def testCommonParse(self):
        """Tests various flavors of the common parse method."""
        ticket_id = 123456
        key = 'boogity'

        # Should parse all values.
        id, api_key, op = self.registration._common_parse(
                (ticket_id, 'finalize',),
                dict(key=key), operation_ok=True)
        self.assertEquals(ticket_id, id)
        self.assertEquals(key, api_key)
        self.assertEquals('finalize', op)

        # Missing op.
        id, api_key, op = self.registration._common_parse((ticket_id,),
                                                          dict(key=key))
        self.assertEquals(ticket_id, id)
        self.assertEquals(key, api_key)
        self.assertIsNone(op)

        # Missing key.
        id, api_key, op = self.registration._common_parse((ticket_id,), dict())
        self.assertEquals(ticket_id, id)
        self.assertIsNone(api_key)
        self.assertIsNone(op)

        # Missing all.
        id, api_key, op = self.registration._common_parse(tuple(), dict())
        self.assertIsNone(id)
        self.assertIsNone(api_key)
        self.assertIsNone(op)

        # Too many args.
        self.assertRaises(server_errors.HTTPError,
                          self.registration._common_parse,
                          (ticket_id, 'lame', 'stuff',), dict())

        # Operation when it's not expected.
        self.assertRaises(server_errors.HTTPError,
                          self.registration._common_parse,
                          (ticket_id, 'finalize'), dict())


    def testFinalize(self):
        """Tests that the finalize workflow does the right thing."""
        # Unclaimed ticket
        self.tickets[(1234, None)] = dict(id=1234)
        self.assertRaises(server_errors.HTTPError,
                          self.registration.POST, 1234, 'finalize')

        # Claimed ticket
        expected_ticket = dict(id=1234, userEmail='buffet@tasty.org')
        self.tickets[(1234, None)] = expected_ticket
        returned_json = json.loads(self.registration.POST(1234, 'finalize'))

        self.assertEquals(returned_json['id'], expected_ticket['id'])
        self.assertEquals(returned_json['userEmail'],
                          expected_ticket['userEmail'])
        self.assertIn('robotAccountEmail', returned_json)
        self.assertIn('robotAccountAuthorizationCode', returned_json)


    def testClaim(self):
        """Tests that we can claim a ticket."""
        self.tickets[(1234, None)] = dict(id=1234)
        self.mox.StubOutWithMock(common_util, 'grab_header_field')
        self.mox.StubOutWithMock(common_util, 'parse_serialized_json')
        update_ticket = dict(userEmail='me')
        common_util.parse_serialized_json().AndReturn(update_ticket)
        common_util.grab_header_field('Authorization').AndReturn(
                'Bearer %s' % self.registration.TEST_ACCESS_TOKEN)

        self.mox.ReplayAll()
        returned_json = json.loads(self.registration.PATCH(1234))
        self.assertIn('userEmail', returned_json)
        # This should have changed to an actual user.
        self.assertNotEquals(returned_json['userEmail'], 'me')
        self.mox.VerifyAll()


    def testInsert(self):
        """Tests that we can create a new ticket."""
        self.mox.StubOutWithMock(common_util, 'parse_serialized_json')
        common_util.parse_serialized_json().AndReturn(None)

        self.mox.ReplayAll()
        returned_json = json.loads(self.registration.POST())
        self.assertIn('id', returned_json)
        self.mox.VerifyAll()


    def testGet(self):
        """Tests that we can retrieve a ticket correctly."""
        self.tickets[(1234, None)] = dict(id=1234)
        returned_json = json.loads(self.registration.GET(1234))
        self.assertEquals(returned_json, self.tickets[(1234, None)])

        # Non-existing ticket.
        self.assertRaises(server_errors.HTTPError,
                          self.registration.GET, 1235)


    def testPatchTicket(self):
        """Tests that we correctly patch a ticket."""
        expected_ticket = dict(id=1234, blah='hi')
        update_ticket = dict(blah='hi')
        self.tickets[(1234, None)] = dict(id=1234)

        self.mox.StubOutWithMock(common_util, 'parse_serialized_json')

        common_util.parse_serialized_json().AndReturn(update_ticket)

        self.mox.ReplayAll()
        returned_json = json.loads(self.registration.PATCH(1234))
        self.assertEquals(expected_ticket, returned_json)
        self.mox.VerifyAll()


    def testReplaceTicket(self):
        """Tests that we correctly replace a ticket."""
        update_ticket = dict(id=12345, blah='hi')
        self.tickets[(12345, None)] = dict(id=12345)

        self.mox.StubOutWithMock(common_util, 'parse_serialized_json')

        common_util.parse_serialized_json().AndReturn(update_ticket)

        self.mox.ReplayAll()
        returned_json = json.loads(self.registration.PUT(12345))
        self.assertEquals(update_ticket, returned_json)
        self.mox.VerifyAll()

        self.mox.ResetAll()

        # Ticket id doesn't match.
        update_ticket = dict(id=12346, blah='hi')
        common_util.parse_serialized_json().AndReturn(update_ticket)

        self.mox.ReplayAll()
        self.assertRaises(server_errors.HTTPError,
                          self.registration.PUT, 12345)
        self.mox.VerifyAll()


if __name__ == '__main__':
    unittest.main()
