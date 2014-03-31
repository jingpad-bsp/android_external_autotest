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
from cros_lib.fake_device_server import registration_tickets
from cros_lib.fake_device_server import resource_delegate


def stop_server():
    """Stops the cherrypy server and blocks."""
    cherrypy.engine.stop()


def start_server():
    """Starts the cherrypy server and blocks."""
    tickets = resource_delegate.ResourceDelegate({})
    registration_tickets_handler = registration_tickets.RegistrationTickets(
            tickets)
    cherrypy.tree.mount(
        registration_tickets_handler, '/clouddevices/v1/registrationTickets',
        {'/':
            {'request.dispatch': cherrypy.dispatch.MethodDispatcher()}
        }
    )
    cherrypy.engine.start()


def main():
    """Main method for callers who start this module directly."""
    start_server()
    cherrypy.engine.block()


if __name__ == '__main__':
    main()
