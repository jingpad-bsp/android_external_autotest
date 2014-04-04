#! /usr/bin/env python

# Copyright 2014 The Chromium OS Authors. All rights reserved.
# Use of this source code is governed by a BSD-style license that can be
# found in the LICENSE file.

"""Fake implementation of a Device Server.

This module can be used in testing both in autotests and locally. To use locally
you can just run this python module directly.
"""

import cherrypy

import common
from cros_lib.fake_device_server import commands
from cros_lib.fake_device_server import devices
from cros_lib.fake_device_server import registration_tickets
from cros_lib.fake_device_server import resource_delegate


def stop_server():
    """Stops the cherrypy server and blocks."""
    cherrypy.engine.stop()


def start_server():
    """Starts the cherrypy server and blocks."""
    commands_resource = resource_delegate.ResourceDelegate({})
    commands_handler = commands.Commands(commands_resource)
    cherrypy.tree.mount(
        commands_handler, '/buffet/commands',
        {'/':
            {'request.dispatch': cherrypy.dispatch.MethodDispatcher()}
        }
    )
    devices_resource = resource_delegate.ResourceDelegate({})
    devices_handler = devices.Devices(devices_resource, commands_handler)
    cherrypy.tree.mount(
        devices_handler, '/buffet/devices',
        {'/':
            {'request.dispatch': cherrypy.dispatch.MethodDispatcher()}
        }
    )
    tickets = resource_delegate.ResourceDelegate({})
    registration_tickets_handler = registration_tickets.RegistrationTickets(
            tickets, devices_handler)
    cherrypy.tree.mount(
        registration_tickets_handler, '/buffet/registrationTickets',
        {'/':
            {'request.dispatch': cherrypy.dispatch.MethodDispatcher()}
        }
    )
    # Don't parse POST for params.
    cherrypy.config.update({'global': {'request.process_request_body': False}})
    cherrypy.engine.start()


def main():
    """Main method for callers who start this module directly."""
    start_server()
    cherrypy.engine.block()


if __name__ == '__main__':
    main()
