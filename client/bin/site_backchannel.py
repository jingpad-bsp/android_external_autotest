# Copyright (c) 2010 The Chromium OS Authors. All rights reserved.
# Use of this source code is governed by a BSD-style license that can be
# found in the LICENSE file.
import logging, os, subprocess
from autotest_lib.client.common_lib import error, utils


# Flag file used to tell backchannel script it's okay to run.
BACKCHANNEL_FILE = '/mnt/stateful_partition/etc/enable_backchannel_network'


def setup(interface='eth0', create_ssh_routes=True, additional_routes=[]):
    """Enables the backchannel interface and if specified creates routes so that
    all existing SSH sessions will remain open. Additional IPs for which routes
    should be created may also be specified."""

    # Retrieve the gateway for the default route.
    try:
      gateway = utils.system_output(
          "route | grep default | awk '{print $2}'").split('\n')[0].strip()

      # Retrieve list of open ssh sessions so we can reopen routes afterward.
      if create_ssh_routes:
        out = utils.system_output(
            "netstat -tanp | grep :22 | grep ESTABLISHED | awk '{print $5}'")

        # Extract IP from IP:PORT listing
        open_ssh = list(item.strip().split(':')[0] for item in out.split('\n')
                       if item.strip())

      # Create backchannel file flag.
      open(BACKCHANNEL_FILE, 'w').close()

      # Turn on back channel. Will throw exception on non-zero exit.
      utils.system('/sbin/backchannel-setup %s' % interface)

      # Create routes so existing SSH sessions will stay open plus any other
      # routes that have been specified by the caller.
      if create_ssh_routes:
        for ip in open_ssh + additional_routes:
          # Convert IP to CIDR format.
          cidr = ip[:ip.rindex('.') + 1] + '0/24'

          # Add route using the pre-backchannel gateway.
          utils.system('route add -net %s gw %s' % (cidr, gateway))
    except Exception, e:
      logging.error(e)
      return False
    finally:
      # Remove backchannel file flag so system reverts to normal on reboot.
      if os.path.isfile(BACKCHANNEL_FILE):
        os.remove(BACKCHANNEL_FILE)

    return True
