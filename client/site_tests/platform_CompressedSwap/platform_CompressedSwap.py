#!/usr/bin/python
#
# Copyright (c) 2012 The Chromium Authors. All rights reserved.
# Use of this source code is governed by a BSD-style license that can be
# found in the LICENSE file.

import logging, os, select, signal, subprocess, time

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

    # Check for low memory notification by polling /dev/chromeos-low-mem.
    def getting_low_mem_notification(self):
        lowmem_fd = open('/dev/chromeos-low-mem', 'r')
        lowmem_poller = select.poll()
        lowmem_poller.register(lowmem_fd, select.POLLIN)
        events=lowmem_poller.poll(0)
        lowmem_fd.close()
        for fd, flag in events:
            if flag & select.POLLIN:
                return True
        return False

    def run_once(self, just_checking_lowmem=False):

        memtotal = utils.read_from_meminfo('MemTotal')
        swaptotal = utils.read_from_meminfo('SwapTotal')
        if just_checking_lowmem:
            # When just checking for low mem notification, swaptotal is
            # allowed to be 0.  If it is, set swaptotal to memtotal.
            if swaptotal == 0:
                swaptotal = memtotal
        else:
            # Verify we set /sys/block/zram0/disksize to approximately 3/2 of
            # MemTotal as per /etc/swap.conf.
            swap_target = memtotal * 3 / 2
            if swaptotal == 0:
                raise error.TestFail('SwapTotal is 0, swap is configured off.')
            if swaptotal < swap_target / 2 or swaptotal > swap_target * 3 / 2:
                raise error.TestFail('SwapTotal %d is nowhere near our ' \
                    'target of %d.' % (swaptotal, swap_target))

        got_low_mem_notification = False
        cleared_low_mem_notification = False

        # Loop over hog creation until MemFree+SwapFree approaches 0.
        # Confirm we do not see any OOMs (procs killed due to Out Of Memory).
        hogs = []
        cmd = [ self.srcdir + '/' + self.executable, '50' ]
        logging.debug('Memory hog command line is %s' % cmd)
        while len(hogs) < 200:
            memfree = utils.read_from_meminfo('MemFree')
            swapfree = utils.read_from_meminfo('SwapFree')
            total_free = memfree + swapfree
            logging.debug('nhogs %d: memfree %d, swapfree %d' %
                          (len(hogs), memfree, swapfree))
            if total_free < swaptotal * 0.03:
                break;

            p = subprocess.Popen(cmd)
            utils.write_one_line('/proc/%d/oom_score_adj' % p.pid, '1000')
            hogs.append(p)

            time.sleep(2)

            if self.check_for_oom(hogs):
                utils.system("killall -TERM hog")
                raise error.TestFail('Oom detected after %d hogs created' %
                                     len(hogs))

            # Check for low memory notification.
            if self.getting_low_mem_notification():
                if not got_low_mem_notification:
                    first_notification = len(hogs)
                got_low_mem_notification = True
                logging.info('Got low memory notification after hog %d' %
                             len(hogs))

        logging.info('Finished creating %d hogs, SwapFree %d, MemFree %d' %
                     (len(hogs), swapfree, memfree))

        # Before cleaning up all the hogs, verify that killing hogs back to
        # our initial low memory notification causes notification to end.
        if got_low_mem_notification:
            hogs_killed = 0;
            for p in hogs:
                if not self.getting_low_mem_notification():
                    cleared_low_mem_notification = True
                    logging.info('Cleared low memory notification after %d '
                                 'hogs were killed' % hogs_killed)
                    break;
                p.kill()
                hogs_killed += 1
                time.sleep(2)

        # Clean up the rest of our hogs since they otherwise live forever.
        utils.system("killall -TERM hog")
        time.sleep(5)
        swapfree2 = utils.read_from_meminfo('SwapFree')
        logging.info('SwapFree was %d before cleanup, %d after.' %
                     (swapfree, swapfree2))

        # Raise exceptions due to low memory notification failures.
        if not got_low_mem_notification:
            raise error.TestFail('We did not get low memory notification!')
        elif not cleared_low_mem_notification:
            raise error.TestFail('We did not clear low memory notification!')
        elif len(hogs) - hogs_killed < first_notification - 3:
            raise error.TestFail('We got low memory notification at hog %d, '
                                 'but we did not clear it until we dropped to '
                                 'hog %d' %
                                 (first_notification, len(hogs) - hogs_killed))
