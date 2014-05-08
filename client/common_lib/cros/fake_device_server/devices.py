# Copyright 2014 The Chromium OS Authors. All rights reserved.
# Use of this source code is governed by a BSD-style license that can be
# found in the LICENSE file.

"""Module contains a simple implementation of the devices RPC."""

from cherrypy import tools

import common
from fake_device_server import common_util
from fake_device_server import resource_method
from fake_device_server import server_errors


# TODO(sosa): All access to this object should technically require auth. Create
# setters/getters for the auth token for testing.

DEVICES_PATH = 'devices'


class Devices(resource_method.ResourceMethod):
    """A simple implementation of the device interface.

    A common workflow of using this API is:

    POST .../ # Creates a new device with id <id>.
    PATCH ..../<id> # Update device state.
    GET .../<id> # Get device state.
    DELETE .../<id> # Delete the device.
    """

    # Needed for cherrypy to expose this to requests.
    exposed = True

    # Requires keys in device_config to create a device.
    required_keys = ['systemName', 'deviceKind', 'channel']



    def __init__(self, resource, commands_instance):
        """Initializes a registration ticket.

        @param resource: A resource delegate for storing devices.
        @param commands_instance: Instance of commands method class.
        """
        super(Devices, self).__init__(resource)
        self.commands_instance = commands_instance


    def create_device(self, api_key, device_config):
        """Creates a new device given the device_config.

        @param api_key: Api key for the application.
        @param device_config: Json dict for the device.
        @raises server_errors.HTTPError: if the config is missing a required key
        """
        # Verify required keys exist in the device draft.
        if not device_config:
            raise server_errors.HTTPError(400, 'Empty device draft.')

        for key in self.required_keys:
            if key not in device_config:
                raise server_errors.HTTPError(400, 'Must specify %s' % key)

        # Create default state.
        device_config['kind'] = 'clouddevices#device'
        device_config['state'] = { 'version': '',
                                   'base': { 'connectionStatus': 'online'},
                                 }
        device_config['etag'] = '0' # SOMETHING RANDOM
        device_config['owner'] = '0' # GET OWNER

        new_device = self.resource.update_data_val(None, api_key,
                                                   data_in=device_config)
        self.commands_instance.new_device(new_device['id'], api_key)
        return new_device


    @tools.json_out()
    def GET(self, *args, **kwargs):
        """GET .../(device_id) gets device info or lists all devices.

        Supports both the GET / LIST commands for devices. List lists all
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
            listing = {'kind': 'clouddevices#devicesListResponse'}
            listing['devices'] = self.resource.get_data_vals()
            return listing


    @tools.json_out()
    def POST(self, *args, **kwargs):
        """Creates a new device using the incoming json data."""
        id, api_key, _ = common_util.parse_common_args(args, kwargs)
        data = common_util.parse_serialized_json()

        if id:
            raise server_errors.HTTPError(400, 'Cannot pass an id to INSERT')
        if not data:
            data = {}

        return self.create_device(api_key, data)


    def DELETE(self, *args, **kwargs):
        """Deletes the given device.

        Format of this call is:
        DELETE .../device_id

        Raises:
            server_errors.HTTPError if the device doesn't exist.
        """
        id, api_key, _ = common_util.parse_common_args(args, kwargs)
        self.resource.del_data_val(id, api_key)
        self.commands_instance.remove_device(id, api_key)
