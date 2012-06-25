# Copyright (c) 2012 The Chromium OS Authors. All rights reserved.
# Use of this source code is governed by a BSD-style license that can be
# found in the LICENSE file.

import logging
import time

from autotest_lib.client.bin import test, utils
from autotest_lib.client.common_lib import error
from autotest_lib.client.cros import cros_ui_test

class platform_MemoryPressure(cros_ui_test.UITest):
    version = 1

    def run_once(self):
        perf_results = {}
        tab_open_period = 1.5  # seconds
        timeout = 120  # seconds
        time_limit = time.time() + timeout
        # start observing pyauto events
        event_id = self.pyauto.AddPyAutoEventObserver(recurring = True)
        # Open tabs until a tab discard notification arrives, or a time limit
        # is reached.
        while True:
            # The program in js-bloat.html allocates a few large arrays and
            # forces them in memory by touching some of their elements.
            self.pyauto.AppendTab("file://%s/js-bloat.html" % self.srcdir)
            time.sleep(tab_open_period)
            e = self.pyauto.GetNextEvent(event_id, blocking=False)
            logging.info("received event: %s" % e)
            if e and e.get('event_name') == 'tab_discard':
                break
            if time.time() > time_limit:
                e = None
                break;
        n_tabs = self.pyauto.GetTabCount()
        if e:
            logging.info("tab discard after %d tabs", n_tabs)
        else:
            msg = "FAIL: no tab discard after opening %d tabs in %ds" % \
                (n_tabs, timeout)
            logging.error(msg)
            raise error.TestError(msg)
        perf_results["NumberOfTabsAtFirstDiscard"] = n_tabs
        self.write_perf_keyval(perf_results)
