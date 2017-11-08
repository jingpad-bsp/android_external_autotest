#!/usr/bin/python
# Copyright 2017 The Chromium Authors. All rights reserved.
# Use of this source code is governed by a BSD-style license that can be
# found in the LICENSE file.

"""This tool manages the lxc container pool service."""

import argparse
import logging
import os
import signal
from contextlib import contextmanager

import common
from autotest_lib.client.bin import utils
from autotest_lib.client.common_lib import logging_config
from autotest_lib.site_utils import lxc
from autotest_lib.site_utils.lxc import container_pool


def _start(_args):
    """Starts up the container pool service.

    This function instantiates and starts up the pool service on the current
    thread (i.e. the function will block, and not return until the service is
    shut down).
    """
    # TODO(dshi): crbug.com/459344 Set remove this enforcement when test
    # container can be unprivileged container.
    if utils.sudo_require_password():
        logging.warning('SSP requires root privilege to run commands, please '
                        'grant root access to this process.')
        utils.run('sudo true')
    host_dir = lxc.SharedHostDir()
    service = container_pool.Service(host_dir)
    # Catch Ctrl-C, and send the appropriate stop request to the service instead
    # of trying to kill the main thread.
    signal.signal(signal.SIGINT, lambda s, f: service.stop())
    # Start the service.  This blocks and does not return till the service shuts
    # down.
    service.start()


def _status(_args):
    """Requests status from the running container pool.

    The retrieved status is printed out via logging.
    """
    with _create_client() as client:
        logging.debug('Requesting status...')
        logging.info(client.get_status())


def _stop(_args):
    """Shuts down the running container pool."""
    with _create_client() as client:
        logging.debug('Requesting stop...')
        logging.info(client.shutdown())


@contextmanager
# TODO(kenobi): Don't hard-code the timeout.
def _create_client(timeout=3):
    logging.debug('Creating client...')
    # TODO(kenobi): Don't hard-code the address
    address = os.path.join(lxc.SharedHostDir().path,
                           'container_pool_socket')
    with container_pool.Client.connect(address, timeout) as connection:
        yield connection


def parse_args():
    """Parse command line inputs.

    @raise argparse.ArgumentError: If command line arguments are invalid.
    """
    parser = argparse.ArgumentParser()
    subparsers = parser.add_subparsers()

    parser_start = subparsers.add_parser('start')
    parser_start.set_defaults(func = _start)

    parser_stop = subparsers.add_parser('stop')
    parser_stop.set_defaults(func = _stop)

    parser_status = subparsers.add_parser('status')
    parser_status.set_defaults(func = _status)

    options = parser.parse_args()
    return options


def main():
    """Main function."""
    # Configure logging.
    config = logging_config.LoggingConfig()
    config.configure_logging()

    # Parse args, then dispatch control to the appropriate helper.
    args = parse_args()
    args.func(args)


if __name__ == '__main__':
    main()
