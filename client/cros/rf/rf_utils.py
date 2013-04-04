# Copyright (c) 2012 The Chromium OS Authors. All rights reserved.
# Use of this source code is governed by a BSD-style license that can be
# found in the LICENSE file.

import logging
import re

import common
from autotest_lib.client.common_lib import error, utils
from cros.factory.utils import net_utils

def SetEthernetIp(ip, interface=None):
    '''Sets the IP address for Ethernet.

    The address is set only if the interface does not already have an
    assigned IP address. The interface will be automatically assigned by
    Connection Manager if None is given.
    '''
    interface = interface or net_utils.FindUsableEthDevice()
    if not interface:
        raise error.TestError('No Ethernet interface available')
    utils.system('ifconfig %s up' % interface)

    ip_output = utils.system_output(
        'ip addr show dev %s' % interface)
    match = re.search('^\s+inet ([.0-9]+)', ip_output, re.MULTILINE)
    if match:
        logging.info('Not setting IP address for interface %s: '
                     'already set to %s' % (interface, match.group(1)))
        return
    utils.system('ifconfig %s %s' % (interface, ip))

def IsInRange(observed, min, max):
    '''Returns True if min <= observed <= max.

    If either min or max is None, then the comparison will always succeed.
    '''
    if min and observed < min:
        return False
    if max and observed > max:
        return False
    return True
