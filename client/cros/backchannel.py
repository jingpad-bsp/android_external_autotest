# Copyright (c) 2012 The Chromium OS Authors. All rights reserved.
# Use of this source code is governed by a BSD-style license that can be
# found in the LICENSE file.

import logging, os

from autotest_lib.client.bin import utils
from autotest_lib.client.common_lib import error

# Flag file used to tell backchannel script it's okay to run.
BACKCHANNEL_FILE = '/mnt/stateful_partition/etc/enable_backchannel_network'


class Backchannel(object):
    """Wrap backchannel in a context manager so it can be used with with.

    Example usage:
         with backchannel.Backchannel():
                block
    The backchannel will be torn down whether or not 'block' throws.
    """

    def __init__(self, *args, **kwargs):
        self.args = args
        self.kwargs = kwargs
        self.interface = None

    def __enter__(self):
        self.setup(*self.args, **self.kwargs)
        return self

    def __exit__(self, exception, value, traceback):
        self.teardown()
        return False

    def setup(self, create_ssh_routes=True):
        """
        Enables the backchannel interface.

        @param create_ssh_routes: If True set up routes so that all existing
                SSH sessions will remain open.

        @returns True if the backchannel is already set up, or was set up by
                this call, otherwise False.

        """

        # If the backchannel interface is already up there's nothing
        # for us to do.
        if is_network_iface_running('eth_test'):
            return True

        # Retrieve the gateway for the default route.
        try:
            # Poll here until we have route information.
            # If shill was recently started, it will take some time before
            # DHCP gives us an address.
            utils.poll_for_condition(
                    lambda: get_route_information(),
                    exception=utils.TimeoutError(
                            'Timed out waiting for route information'),
                    timeout=30)
            line = get_route_information()
            gateway, self.interface = line.strip().split(' ')

            # Retrieve list of open ssh sessions so we can reopen
            # routes afterward.
            if create_ssh_routes:
                out = utils.system_output(
                        "netstat -tanp | grep :22 | "
                        "grep ESTABLISHED | awk '{print $5}'")

                # Extract IP from IP:PORT listing. Uses set to remove
                # duplicates.
                open_ssh = list(set(item.strip().split(':')[0] for item in
                                    out.split('\n') if item.strip()))

            backchannel('setup %s' % self.interface)

            # Create routes so existing SSH sessions will stay open.
            if create_ssh_routes:
                for ip in open_ssh:
                    # Add route using the pre-backchannel gateway.
                    backchannel('reach %s %s' % (ip, gateway))

            # Make sure we have a route to the gateway before continuing.
            logging.info('Waiting for route to gateway %s', gateway)
            utils.poll_for_condition(
                    lambda: is_route_ready(gateway),
                    exception=utils.TimeoutError('Timed out waiting for route'),
                    timeout=30)
        except Exception, e:
            logging.error(e)
            return False
        finally:
            # Remove backchannel file flag so system reverts to normal
            # on reboot.
            if os.path.isfile(BACKCHANNEL_FILE):
                os.remove(BACKCHANNEL_FILE)

        return True

    def teardown(self):
        """Tears down the backchannel."""
        if self.interface:
            backchannel('teardown %s' % self.interface)


def backchannel(args):
    """Launches the backchannel script that does the heavy lifting."""
    # TODO(pprabhu): Switch to use python version of backchannel
    # (crbug.com/259539).
    utils.system('/usr/local/lib/flimflam/test/backchannel %s' % args)


def is_network_iface_running(name):
    """
    Checks to see if the interface is running.

    @param name: Name of the interface to check.

    @returns True if the interface is running.

    """
    try:
        out = utils.system_output('ifconfig %s' % name)
    except error.CmdError, e:
        logging.info(e)
        return False

    return out.find('RUNNING') >= 0


def get_route_information():
    """
    Retrieves the default route information.

    @returns a string that contains the gateway address and the interface.
            If no route information is available, returns an empty string.

    """
    return utils.system_output(
            "route -n | awk '/^0.0.0.0/ { print $2, $8 }'").split('\n')[0]


def is_route_ready(dest):
    """
    Checks to see if there is a route to the specified destination.

    @param dest: IP address of the destination to check.

    @returns True if there is a route to |dest|.

    """
    try:
        out = utils.system_output('ping -c 1 %s' % dest)
    except error.CmdError, e:
        logging.error(e)
        return False

    return True
