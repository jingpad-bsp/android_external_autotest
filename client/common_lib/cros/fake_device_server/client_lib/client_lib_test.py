#! /usr/bin/python

# Copyright 2014 The Chromium OS Authors. All rights reserved.
# Use of this source code is governed by a BSD-style license that can be
# found in the LICENSE file.

"""Small integration test for registration client."""

import sys
import urllib2

import commands
import devices
import registration


def main():
    """Main method for integration test."""
    r_client = registration.RegistrationClient()
    new_device = r_client.register_device('test_device', 'vendor', 'xmpp')
    print 'Registered new device', new_device

    d_client = devices.DevicesClient()
    if not d_client.get_device(new_device['id']):
        print 'Device not found in database'
        return 1

    device_list = d_client.list_devices()['devices']
    device_ids = [device['id'] for device in device_list]
    if not new_device['id'] in device_ids:
        print 'Device found but not listed correctly'
        return 1

    c_client = commands.CommandsClient()
    command_dict = {
            'base': {
                    'reboot': {'kind': 'clouddevices#commandBaseReboot'}
                    }
            }
    new_command = c_client.create_command(device['id'], command_dict)
    if not c_client.get_command(new_command['id']):
        print 'Command not found'
        return 1

    command_list = c_client.list_commands(device['id'])['commands']
    command_ids = [c['id'] for c in command_list]
    if not new_command['id'] in command_ids:
        print 'Command found but not listed correctly'
        return 1

    new_command = c_client.update_command(new_command['id'],
                                          {'state':'finished'})
    return 0


if __name__ == '__main__':
    try:
        error_code = main()
        if error_code != 0:
            print 'Test Failed'

        sys.exit(error_code)
    except urllib2.HTTPError as e:
        print e.read()
        sys.exit(1)
