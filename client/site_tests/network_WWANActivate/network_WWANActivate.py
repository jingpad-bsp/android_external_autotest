# Copyright (c) 2012 The Chromium OS Authors. All rights reserved.
# Use of this source code is governed by a BSD-style license that can be
# found in the LICENSE file.

from autotest_lib.client.bin import test, utils
from autotest_lib.client.common_lib import error
from autotest_lib.client.cros import sys_power

import logging, time

class network_WWANActivate(test.test):
    version = 1

    def run_once(self, interface='wwan0', deadline=1.1, repeat=1):
        """Check that the WWAN device comes up after a resume

        @param interface: The device associated with the WWAN hardware
        @param deadline: Seconds to wait for the device
        @param repeat: number of times to carry out the test
        """
        for i in range(0, repeat):
            logging.info('Test run %d', i)
            sys_power.suspend_to_ram(3)
            wait = wait_for_modem(deadline, interface, deadline/10)
            logging.info('%.2f seconds to modem activation', wait)


def wait_for_modem(deadline, interface, delay):
    """Wait for the interface to appear.

    Raise a test error if more than |deadline| seconds pass without
    |interface| becoming available.

    @param deadline: seconds to wait after which the test will fail
    @param interface: the interface name
    @param delay: seconds to wait between checks for |interface|
    """
    if deadline < delay:
        raise error.TestError('Intra-check delay cannot exceed WWAN deadline.')

    cycles = int(deadline / delay)
    modem = False
    ifconfig = 'ifconfig %s 2>/dev/null' % interface

    for i in range(0, cycles):
        try:
            utils.system(ifconfig)
        except error.CmdError:
            time.sleep(delay)
            continue

        modem = True
        break

    if not modem:
        raise error.TestFail('Modem not up within %f seconds.' % deadline)
    return i * delay
