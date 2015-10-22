# Copyright 2015 The Chromium OS Authors. All rights reserved.
# Use of this source code is governed by a BSD-style license that can be
# found in the LICENSE file.

import argparse
import logging

import common
from autotest_lib.client.common_lib import error
from autotest_lib.server import hosts
from autotest_lib.server.hosts import moblab_host


_LOGGING_FORMAT = '%(asctime)s - %(levelname)s - %(message)s'

# Running against a virtual machine has several intricacies that we need to
# adjust for. Namely SSH requires the use of 'localhost' while HTTP requires
# the use of '127.0.0.1'. Also because we are forwarding the ports from the VM
# to the host system, the ports to use for these services are also different
# from running on a physical machine.
_VIRT_MACHINE_SSH_ADDR = 'localhost:9222'
_VIRT_MACHINE_AFE_ADDR = '127.0.0.1:8888'
_VIRT_MACHINE_DEVSERVER_PORT = '7777'
_PHYS_MACHINE_DEVSERVER_PORT = '8080'


class BrilloTestError(Exception):
    """A general error while testing Brillo."""


class BrilloMoblabInitializationError(BrilloTestError):
    """An error during Moblab initialization or handling."""


def get_moblab_and_devserver_port(moblab_hostname):
    """Initializes and returns a MobLab Host Object.

    @params moblab_hostname: The Moblab hostname, None if using a local virtual
                             machine.

    @returns A pair consisting of a MoblabHost and a devserver port.

    @raise BrilloMoblabInitializationError: Failed to set up the Moblab.
    """
    if moblab_hostname:
        web_address = moblab_hostname
        devserver_port = _PHYS_MACHINE_DEVSERVER_PORT
        rpc_timeout_min = 2
    else:
        moblab_hostname = _VIRT_MACHINE_SSH_ADDR
        web_address = _VIRT_MACHINE_AFE_ADDR
        devserver_port = _VIRT_MACHINE_DEVSERVER_PORT
        rpc_timeout_min = 5

    try:
        host = hosts.create_host(moblab_hostname,
                                 host_class=moblab_host.MoblabHost,
                                 web_address=web_address,
                                 retain_image_storage=True,
                                 rpc_timeout_min=rpc_timeout_min)
    except error.AutoservRunError as e:
        raise BrilloMoblabInitializationError(
                'Unable to connect to the MobLab: %s' % e)

    try:
        host.afe.get_hosts()
    except Exception as e:
        raise BrilloMoblabInitializationError(
                "Unable to communicate with the MobLab's web frontend, "
                "please verify that it is up and running at http://%s/\n"
                "Error: %s" % (host.web_address, e))

    return host, devserver_port


def parse_args(description, setup_parser=None, validate_args=None):
    """Parse command-line arguments.

    @param description: The script description in the help message.
    @param setup_parser: Function that takes a parser object and adds
                         script-specific options to it.
    @param validate_args: Function that takes a parser object and the parsed
                          arguments and validates the arguments. It should use
                          parser.error() to report errors.

    @return Parsed and validated arguments.
    """
    parser = argparse.ArgumentParser(description=description)
    if setup_parser:
        setup_parser(parser)

    # Add common options.
    parser.add_argument('-m', '--moblab_host',
                        help='MobLab hostname or IP to launch tests. If this '
                             'argument is not provided, the test launcher '
                             'will attempt to test a local virtual machine '
                             'instance of MobLab.')
    parser.add_argument('-a', '--adb_host',
                        help='Hostname or IP of the adb_host connected to the '
                             'Brillo DUT. Default is to assume it is connected '
                             'directly to the MobLab.')
    parser.add_argument('-d', '--debug', action='store_true',
                        help='Print log statements.')

    args = parser.parse_args()

    # Configure the root logger.
    logging.getLogger().setLevel(logging.DEBUG if args.debug else logging.INFO)
    for log_handler in logging.getLogger().handlers:
        log_handler.setFormatter(logging.Formatter(fmt=_LOGGING_FORMAT))

    if validate_args:
        validate_args(parser, args)

    return args
