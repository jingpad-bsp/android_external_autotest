# Copyright 2014 The Chromium OS Authors. All rights reserved.
# Use of this source code is governed by a BSD-style license that can be
# found in the LICENSE file.

"""Module contains a simple implementation of the commands RPC."""

from cherrypy import tools
import logging

import common
from fake_device_server import common_util
from fake_device_server import constants
from fake_device_server import resource_method
from fake_device_server import server_errors

COMMANDS_PATH = 'commands'


# TODO(sosa) Support upload method (and mediaPath parameter).
class Commands(resource_method.ResourceMethod):
    """A simple implementation of the commands interface."""

    # Needed for cherrypy to expose this to requests.
    exposed = True

    # Roots of command resource representation that might contain commands.
    _COMMAND_ROOTS = set(['base', 'aggregator', 'printer', 'storage'])


    def __init__(self, resource):
        """Initializes a registration ticket.

        @param resource: A resource delegate.
        """
        super(Commands, self).__init__(resource)

        # Maps devices to commands.
        self.device_commands = dict()


    def new_device(self, device_id, api_key):
        """Adds knowledge of a device with the given |device_id|.

        This method should be called whenever a new device is created. It
        populates an empty command dict for each device state.

        @param device_id: Device id to add.
        @param api_key: key for the application.
        """
        self.device_commands[(device_id, api_key)] = {}


    def remove_device(self, device_id, api_key):
        """Removes knowledge of the given device.

        @param device_id: Device id to remove.
        @param api_key: key for the application.
        """
        del self.device_commands[(device_id, api_key)]


    def create_command(self, api_key, device_id, command_config):
        """Creates, queues and returns a new command.

        @param api_key: Api key for the application.
        @param device_id: Device id of device to send command.
        @param command_config: Json dict for command.
        """
        if (device_id, api_key) not in self.device_commands.keys():
            raise server_errors.HTTPError(400, 'Unknown device with id %s' %
                                          device_id)

        # We only need to verify that a command is specified (and only one
        # command is specified).
        many_command_error = 'Either no commands or multiple commands specified'

        command_key_set = self._COMMAND_ROOTS.intersection(
                set(command_config.keys()))
        if len(command_key_set) != 1:
            # If this isn't exactly 1, then either no commands are specified OR
            # more than one command is specified.
            raise server_errors.HTTPError(400, many_command_error)

        # Tracks the path of the command in the command_config.
        command_parts = [command_key_set.pop()]
        command = command_config[command_parts[0]]

        # All commands must have exactly one entry that is the command one-level
        # down i.e. base.Reboot.*
        if len(command.keys()) != 1:
            raise server_errors.HTTPError(400, many_command_error)

        command_parts.append(command.keys()[0])
        # Print out something useful (command base.Reboot)
        logging.info('Received command %s', '.'.join(command_parts))

        # TODO(sosa): Check to see if command is in devices CDD.
        # Queue command, create it and insert to device->command mapping.
        command_config['state'] = constants.QUEUED_STATE
        new_command = self.resource.update_data_val(None, api_key,
                                                    data_in=command_config)
        self.device_commands[(device_id,
                              api_key)][new_command['id']] = new_command
        return new_command


    @tools.json_out()
    def GET(self, *args, **kwargs):
        """GET .../(command_id) gets command info or lists all devices.

        Supports both the GET / LIST commands for commands. List lists all
        devices a user has access to, however, this implementation just returns
        all devices.

        Raises:
            server_errors.HTTPError if the device doesn't exist.
        """
        id, api_key, _ = common_util.parse_common_args(args, kwargs)
        if id:
            return self.resource.get_data_val(id, api_key)
        else:
            # Returns listing (ignores optional parameters).
            listing = {'kind': 'clouddevices#commandsListResponse'}
            device_id = kwargs.get('deviceId')
            if not device_id:
                raise server_errors.HTTPError(400, 'Can only list commands by '
                                              'deviceId.')

            requested_state = kwargs.get('state')
            listing['commands'] = []
            for command in self.device_commands[(device_id, api_key)].values():
                # Check state for match (if None, just append all of them).
                if not requested_state or requested_state == command['state']:
                    listing['commands'].append(command)

            return listing


    @tools.json_out()
    def POST(self, *args, **kwargs):
        """Creates a new device using the incoming json data."""
        id, api_key, _ = common_util.parse_common_args(args, kwargs)
        data = common_util.parse_serialized_json()
        if not data:
            data = {}

        device_id = kwargs.get('deviceId')
        if not device_id:
            raise server_errors.HTTPError(400, 'Can only create a command if '
                                          'you provide a deviceId.')

        return self.create_command(api_key, device_id, data)
