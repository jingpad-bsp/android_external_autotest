#!/usr/bin/python
#
# Copyright (c) 2012 The Chromium Authors. All rights reserved.
# Use of this source code is governed by a BSD-style license that can be
# found in the LICENSE file.

import logging, os, signal, subprocess, time

from autotest_lib.client.bin import utils, test
from autotest_lib.client.common_lib import error


class platform_CompressedSwap(test.test):
    """
    Verify compressed swap is configured and basically works.
    """
    version = 1
    executable = 'hog'

    def setup(self):
        os.chdir(self.srcdir)
        utils.make(self.executable)

    def check_for_oom(self, hogs):
        for p in hogs:
            retcode = p.poll() # returns None if the thread is still running
            if retcode is not None:
                logging.info('hog %d of %d is gone, assume oom: retcode %s' %
                             (hogs.index(p) + 1, len(hogs), retcode))
                return True
        return False

    def run_once(self):

        # Verify we set /sys/block/zram0/disksize to approximately 3/2 of
        # MemTotal as per /etc/swap.conf.
        memtotal = utils.read_from_meminfo('MemTotal')
        swaptotal = utils.read_from_meminfo('SwapTotal')
        swap_target = memtotal * 3 / 2
        if swaptotal == 0:
            raise error.TestFail('SwapTotal is 0, swap is configured off.')
        if swaptotal < swap_target / 2 or swaptotal > swap_target * 3 / 2:
            raise error.TestFail('SwapTotal %d is nowhere near our ' \
                'target of %d.' % (swaptotal, swap_target))

        # Loop over hog creation until MemFree+SwapFree approaches 0.
        # Confirm we do not see any OOMs (procs killed due to Out Of Memory)
        # until we are "reasonably close to 0" (say, 10% of SwapFree).
        hogs = []
        cmd = [ self.srcdir + '/' + self.executable, '100' ]
        logging.debug('Memory hog command line is %s' % cmd)
        while len(hogs) < 100:
            memfree = utils.read_from_meminfo('MemFree')
            swapfree = utils.read_from_meminfo('SwapFree')
            total_free = memfree + swapfree
            logging.debug('nhogs %d: memfree %d, swapfree %d' %
                          (len(hogs), memfree, swapfree))
            if total_free < swaptotal * 0.1:
                break;

            if self.check_for_oom(hogs):
                utils.system("killall -TERM hog")
                raise error.TestFail('Oom detected after %d hogs created' %
                                     len(hogs))

            p = subprocess.Popen(cmd)
            utils.write_one_line('/proc/%d/oom_score_adj' % p.pid, '1000')
            hogs.append(p)
            time.sleep(2)

        logging.info('completed after %d hogs created' % len(hogs))

        # Clean up our hogs since they otherwise live forever.
        # Sending signals via p.send_signal() is insufficient to
        # kill the hogs because it only kills the 'nice' parents,
        # not the actual 'hog' children.
        swapfree1 = utils.read_from_meminfo('SwapFree')
        utils.system("killall -TERM hog")
        time.sleep(5)
        swapfree2 = utils.read_from_meminfo('SwapFree')
        logging.info('SwapFree was %d before cleanup, %d after.' %
                     (swapfree1, swapfree2))
