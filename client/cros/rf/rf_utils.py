# Copyright (c) 2012 The Chromium OS Authors. All rights reserved.
# Use of this source code is governed by a BSD-style license that can be
# found in the LICENSE file.

import logging
import re
import rf_common

from autotest_lib.client.bin import utils

def SetEthernetIp(ip):
    '''Sets the IP address of the first active Ethernet interface.

    The address is set only if the interface does not already have an
    assigned IP address.
    '''
    match = re.match('^(eth\d+)', utils.system_output('ifconfig'))
    if not match:
        raise error.TestError('No Ethernet interface available')
    interface = match.group(1)

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
