#! /usr/bin/python

# Copyright 2017 The Chromium OS Authors. All rights reserved.
# Use of this source code is governed by a BSD-style license that can be
# found in the LICENSE file.

"""
Swarming bot manager running on servers that hold swarming bots.
This manages running swarming bots and routinely recovers any that die.
"""

import argparse
import logging
import signal
import socket
import sys
import time
import urllib2

import common
from autotest_lib.server.cros.dynamic_suite import frontend_wrappers
from autotest_lib.site_utils.chromeos_proxy import swarming_bots

# The seconds between consequent bot check.
CHECK_INTERVAL = 180

_shut_down = False

def _parse_args(args):
    """Parse system arguments."""
    parser = argparse.ArgumentParser(
            description='Manage the set of swarming bots running on a server')
    parser.add_argument('afe', type=str,
                        help='AFE to get server role and status.')
    # TODO(xixuan): refactor together with swarming_bots.
    parser.add_argument(
            'id_range', type=str,
            help='A range of integer, each bot created will be labeled '
                 'with an id from this range. E.g. "1-200"')
    parser.add_argument(
            'working_dir', type=str,
            help='A working directory where bots will store files '
                 'generated at runtime')
    parser.add_argument(
            '-p', '--swarming_proxy', type=str, dest='swarming_proxy',
            default=swarming_bots.DEFAULT_SWARMING_PROXY,
            help='The URL of the swarming instance to talk to, '
                 'Default to the one specified in global config')
    parser.add_argument(
            '-f', '--log_file', dest='log_file',
            help='Path to the log file.')
    parser.add_argument(
            '-v', '--verbose', dest='verbose', action='store_true',
            help='Verbose mode')

    return parser.parse_args(args)


def handle_signal(signum, frame):
    """Function called when being killed.

    @param signum: The signal received.
    @param frame: Ignored.
    """
    del signum
    del frame

    _shut_down = True


def is_server_in_prod(server_name, afe):
    """Validate server's role and status.

    @param server_name: the server name to be validated.
    @param afe: the afe server to get role & status info in server_db.

    @return: A boolean value, True when the server_name is in prod, False
             otherwise, or if RPC fails.
    """
    logging.info('Validating server: %s', server_name)
    afe = frontend_wrappers.RetryingAFE(timeout_min=5, delay_sec=10,
                                        server=afe)
    try:
        if afe.run('get_servers', hostname=server_name,
                   status='primary', role='golo_proxy'):
            return True
        else:
            return False
    except urllib2.URLError as e:
        logging.warning('RPC get_servers failed on afe %s: %s', afe, str(e))
        return False


def main(args):
    """Main func.

    @args: A list of system arguments.
    """
    args = _parse_args(args)
    swarming_bots.setup_logging(args.verbose, args.log_file)

    if not args.swarming_proxy:
        logging.error(
                'No swarming proxy instance specified. '
                'Specify swarming_proxy in [CROS] in shadow_config, '
                'or use --swarming_proxy')
        return 1

    if not args.swarming_proxy.startswith('https://'):
        swarming_proxy = 'https://' + args.swarming_proxy
    else:
        swarming_proxy = args.swarming_proxy

    global _shut_down
    logging.info("Setting signal handler.")
    signal.signal(signal.SIGINT, handle_signal)
    signal.signal(signal.SIGTERM, handle_signal)

    bot_manager = swarming_bots.BotManager(
            swarming_bots.parse_range(args.id_range),
            args.working_dir,
            args.swarming_proxy)
    is_prod = False
    retryable = True
    while not _shut_down:
        if is_server_in_prod(socket.getfqdn(), args.afe):
            bot_manager.check()

        time.sleep(CHECK_INTERVAL)


if __name__ == '__main__':
    sys.exit(main(sys.argv[1:]))
