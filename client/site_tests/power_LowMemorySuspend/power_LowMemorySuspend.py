# Copyright 2018 The Chromium OS Authors. All rights reserved.
# Use of this source code is governed by a BSD-style license that can be
# found in the LICENSE file.

import logging
import time

from autotest_lib.client.bin import test
from autotest_lib.client.bin import utils
from autotest_lib.client.common_lib import error
from autotest_lib.client.common_lib.cros import chrome
from autotest_lib.client.common_lib.cros import arc_util
from autotest_lib.client.cros.power import sys_power


# Stop adding tab when swap_free / swap_total is less than this value.
_LOW_SWAP_THRESHOLD = 0.5
# Terminate the test if active_tabs / created_tabs is less than this value.
_TOO_FEW_ACTIVE_TABS_THRESHOLD = 0.33


class power_LowMemorySuspend(test.test):
    """Low memory suspending stress test."""
    version = 1

    def low_swap_free(self):
        """Returns true if free swap is low."""
        meminfo = utils.get_meminfo()
        if meminfo.SwapFree < meminfo.SwapTotal * _LOW_SWAP_THRESHOLD:
            logging.info("Swap is low, swap free: %d, swap total: %d",
                         meminfo.SwapFree, meminfo.SwapTotal)
            return True
        return False

    def create_tabs(self, cr):
        """Creates tabs until swap free is low."""
        # Any non-trivial web page is suitable to consume memory.
        URL = 'https://inbox.google.com/'
        tabs = []

        # No need to create the first tab as there is already one
        # when the browser is ready.
        tabs.append(cr.browser.tabs[0])
        tabs[0].Navigate(URL);

        while not self.low_swap_free():
            logging.info('creating tab %d', len(tabs))
            tab = cr.browser.tabs.New()
            tabs.append(tab)
            tab.Navigate(URL);
            try:
                tab.WaitForDocumentReadyStateToBeComplete(timeout=20)
            except Exception as e:
                logging.warning('Exception when waiting page ready: %s', e)

        return tabs

    def check_tab_discard(self, cr, tabs):
        """Raise error if too many tabs are discarded."""
        active_tabs = len(cr.browser.tabs)
        created_tabs = len(tabs)
        if (active_tabs < created_tabs * _TOO_FEW_ACTIVE_TABS_THRESHOLD):
            msg = ('Too many discards, active tabs: %d, created tabs: %d' %
                   (active_tabs, created_tabs))
            raise error.TestFail(msg)

    def cycling_suspend(self, cr, tabs, switches_per_suspend,
                        total_suspend_duration, suspend_seconds,
                        additional_sleep):
        """Page cycling and suspending."""
        start_time = time.time()
        suspend_count = 0
        switch_count = 0

        while time.time() - start_time < total_suspend_duration:
            # Page cycling
            for tab in tabs:
                try:
                    tab.Activate()
                    tab.WaitForFrameToBeDisplayed()
                except Exception as e:
                    logging.info('cannot activate tab: %s', e)
                switch_count += 1

                if switch_count % switches_per_suspend == 0:
                    self.check_tab_discard(cr, tabs)

                    # Suspending and resuming after 10 seconds.
                    sys_power.do_suspend(suspend_seconds)
                    suspend_count += 1

                    # Additional waiting for system stable, or the
                    # subsequent tab operations may fail.
                    time.sleep(additional_sleep)

                    self.check_tab_discard(cr, tabs)

        return suspend_count

    def run_once(self, switches_per_suspend=15, total_suspend_duration=3600,
                 suspend_seconds=10, additional_sleep=10):
        """Runs the test once."""
        username, password = arc_util.get_test_account_info()
        with chrome.Chrome(gaia_login=True, username=username,
                           password=password) as cr:
            tabs = self.create_tabs(cr)
            suspend_count = self.cycling_suspend(
                cr, tabs, switches_per_suspend, total_suspend_duration,
                suspend_seconds, additional_sleep)

            tabs_after_suspending = len(cr.browser.tabs)
            meminfo = utils.get_meminfo()
            ending_swap_free = meminfo.SwapFree
            swap_total = meminfo.SwapTotal

        perf_results = {}
        perf_results['number_of_tabs'] = len(tabs)
        perf_results['number_of_suspending'] = suspend_count
        perf_results['tabs_after_suspending'] = tabs_after_suspending
        perf_results['ending_swap_free'] = ending_swap_free
        perf_results['swap_total'] = swap_total
        self.write_perf_keyval(perf_results)

        self.output_perf_value(description='number_of_tabs',
                               value=len(tabs))
        self.output_perf_value(description='number_of_suspending',
                               value=suspend_count)
        self.output_perf_value(description='tabs_after_suspending',
                               value=tabs_after_suspending)
        self.output_perf_value(description='ending_swap_free',
                               value=ending_swap_free, units='KB')
        self.output_perf_value(description='swap_total',
                               value=swap_total, units='KB')

