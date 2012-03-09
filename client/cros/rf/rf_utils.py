# Copyright (c) 2012 The Chromium OS Authors. All rights reserved.
# Use of this source code is governed by a BSD-style license that can be
# found in the LICENSE file.

import logging
import re
import rf_common

from autotest_lib.client.bin import utils

def SetInterfaceIp(interface, ip):
    '''Sets the IP address for a network interface.

    The address is set only if the interface does not already have an
    assigned IP address.
    '''
    ip_output = utils.system_output(
        'ip addr show dev %s' % interface)
    match = re.search('^\s+inet ([.0-9]+)', ip_output, re.MULTILINE)
    if match:
        logging.info('Not setting IP address for interface %s: '
                     'already set to %s' % (interface, match.group(1)))
        return
    utils.system('ifconfig %s %s' % (interface, ip))
