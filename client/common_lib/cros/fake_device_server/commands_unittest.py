#! /usr/bin/python

# Copyright 2014 The Chromium OS Authors. All rights reserved.
# Use of this source code is governed by a BSD-style license that can be
# found in the LICENSE file.

"""Unit tests for commands.py."""

import mox
import unittest

import common
from cros_lib.fake_device_server import commands
from cros_lib.fake_device_server import resource_delegate
from cros_lib.fake_device_server import server_errors


class CommandsTest(mox.MoxTestBase):
    """Tests for the Commands class.

    Note unlike other unittests in this project, I set the api_key for all
    tests. This makes the logic easier to read because of the additional
    dictionary mapping of
    # commands.devices_commands[(id, api_key)] = dict of commands by command id.
    """

    def setUp(self):
        """Sets up mox and a ticket / registration objects."""
        mox.MoxTestBase.setUp(self)
        self.commands_resource = {}
        self.commands = commands.Commands(
                resource_delegate.ResourceDelegate(self.commands_resource))


    def testCreateCommand(self):
        """Tests that we can create a new command."""
        device_id = '1234awesomeDevice'
        api_key = "doesn't matter"
        not_device_id = '1235awesomeDevice'
        self.commands.new_device(device_id, api_key)

        good_command = {'base': { 'vendorCommand': {
                'name': 'specialCommand',
                'kind': 'buffetSpecialCommand', }}}

        new_command = self.commands.create_command(api_key, device_id,
                                                   good_command)
        self.assertTrue('id' in new_command)
        command_id = new_command['id']
        self.assertEqual(new_command['state'], 'queued')
        self.assertEqual(
                self.commands.device_commands[device_id, api_key][command_id],
                new_command)

        # Test bad root name.
        bad_command = {'boogity': { 'vendorCommand': {
                'name': 'specialCommand',
                'kind': 'buffetSpecialCommand', }}}

        self.assertRaises(server_errors.HTTPError,
                          self.commands.create_command, api_key, device_id,
                          bad_command)

        # Test command without necessary nesting.
        bad_command = {'base': {}}
        self.assertRaises(server_errors.HTTPError,
                          self.commands.create_command, api_key, device_id,
                          bad_command)

        # Test adding a good command to an unknown device.
        self.assertRaises(server_errors.HTTPError,
                          self.commands.create_command, api_key, not_device_id,
                          good_command)


    def testGet(self):
        """Tests that we can retrieve a command correctly."""
        api_key = 'APISOCOOL'
        self.commands_resource[(1234, api_key)] = dict(id=1234)
        returned_json = self.commands.GET(1234, key=api_key)
        self.assertEquals(returned_json,
                          self.commands_resource[(1234, api_key)])

        # Non-existing command.
        self.assertRaises(server_errors.HTTPError, self.commands.GET, 1235,
                          key=api_key)


    def testListing(self):
        """Tests that we can get a listing back correctly using the GET method.
        """
        api_key = 'APISOWOW'
        self.commands_resource[(1234, api_key)] = dict(id=1234,
                                                       state='inProgress')
        self.commands_resource[(1235, api_key)] = dict(id=1235,
                                                       boogity='taco',
                                                       state='queued')
        # Add both commands to device1.
        device_id = 'device1'
        self.commands.new_device(device_id, api_key)
        for key, value in self.commands_resource.items():
            self.commands.device_commands[(device_id, api_key)][key[0]] = value

        # Without state should return all commands.
        returned_json = self.commands.GET(deviceId=device_id, key=api_key)
        self.assertEqual('clouddevices#commandsListResponse',
                         returned_json['kind'])
        self.assertTrue('commands' in returned_json)
        returned_command_ids = [command['id']
                                for command in returned_json['commands']]
        for key in self.commands_resource.keys():
            # Key 0 is the command id.
            self.assertIn(key[0], returned_command_ids)

        # Check we can filter by state.
        returned_json = self.commands.GET(deviceId=device_id,
                                          key=api_key,
                                          state='queued')
        self.assertEqual('clouddevices#commandsListResponse',
                         returned_json['kind'])
        self.assertTrue('commands' in returned_json)
        # Only 1235 is queued.
        self.assertIn(self.commands_resource[(1235, api_key)],
                      returned_json['commands'])

        # Sanity check since deviceId or command id is always required to GET.
        self.assertRaises(server_errors.HTTPError, self.commands.GET)


if __name__ == '__main__':
    unittest.main()
