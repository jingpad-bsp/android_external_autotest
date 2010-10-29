# Copyright (c) 2010 The Chromium OS Authors. All rights reserved.
# Use of this source code is governed by a BSD-style license that can be
# found in the LICENSE file.
import logging, os, subprocess
from autotest_lib.client.common_lib import error, utils


# Flag file used to tell backchannel script it's okay to run.
BACKCHANNEL_FILE = '/mnt/stateful_partition/etc/enable_backchannel_network'

def backchannel(args):
    utils.system('/usr/local/lib/flimflam/test/backchannel %s' % args)

def setup(interface='eth0', create_ssh_routes=True):
    """Enables the backchannel interface and if specified creates routes so that
    all existing SSH sessions will remain open."""

    # If the backchannel interface is already up there's nothing for us to do.
    if is_network_iface_running('eth_test'):
      return True

    # Retrieve the gateway for the default route.
    try:
      gateway = utils.system_output(
          "route -n | awk '/^0.0.0.0/ { print $2 }'").split('\n')[0].strip()

      # Retrieve list of open ssh sessions so we can reopen routes afterward.
      if create_ssh_routes:
        out = utils.system_output(
            "netstat -tanp | grep :22 | grep ESTABLISHED | awk '{print $5}'")

        # Extract IP from IP:PORT listing. Uses set to remove duplicates.
        open_ssh = list(set(item.strip().split(':')[0] for item in
                            out.split('\n') if item.strip()))

      backchannel('setup %s' % interface)

      # Create routes so existing SSH sessions will stay open.
      if create_ssh_routes:
        for ip in open_ssh:
          # Add route using the pre-backchannel gateway.
          backchannel('reach %s %s' % (ip, gateway))
    except Exception, e:
      logging.error(e)
      return False
    finally:
      # Remove backchannel file flag so system reverts to normal on reboot.
      if os.path.isfile(BACKCHANNEL_FILE):
        os.remove(BACKCHANNEL_FILE)

    return True

def teardown(interface='eth0'):
  backchannel('teardown %s' % interface)

def is_network_iface_running(name):
    try:
        out = utils.system_output('ifconfig %s' % name)
    except error.CmdError, e:
        logging.info(e)
        return False

    return out.find('RUNNING') >= 0
