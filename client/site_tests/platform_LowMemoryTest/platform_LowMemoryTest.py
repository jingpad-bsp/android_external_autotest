# Copyright (c) 2018 The Chromium OS Authors. All rights reserved.
# Use of this source code is governed by a BSD-style license that can be
# found in the LICENSE file.

import logging
import os
import re
import time

from autotest_lib.client.bin import test
from autotest_lib.client.common_lib import error
from autotest_lib.client.common_lib.cros import chrome
from autotest_lib.client.cros import cros_logging

class MemoryKillsMonitor:
    """A util class for reading kill events."""

    _LOG_FILE = '/var/log/chrome/chrome'
    _PATTERN_DISCARD = re.compile(
        'tab_manager_delegate_chromeos.*:(\d+) Killed tab')
    _PATTERN_OOM = re.compile('Tab OOM-Killed Memory details:')

    def __init__(self):
        self._log_reader = cros_logging.ContinuousLogReader(self._LOG_FILE)

    def check_event(self):
        """Returns the first monitored kill event or empty string"""
        for line in self._log_reader.read_all_logs():
            matched = self._PATTERN_DISCARD.search(line)
            if matched:
                logging.info('Matched line %s', line)
                return 'LOW_MEMORY_KILL_TAB'
            matched = self._PATTERN_OOM.search(line)
            if matched:
                logging.info('Matched line %s', line)
                return 'OOM_KILL'
        return ''


class platform_LowMemoryTest(test.test):
    """Memory pressure test."""
    version = 1

    def create_alloc_page(self, cr, size_mb):
        """The program in alloc.html allocates a large array with random data.
        """
        url = cr.browser.platform.http_server.UrlOf(
            os.path.join(self.bindir, 'alloc.html'))
        url += '?alloc=' + str(size_mb)
        tab = cr.browser.tabs.New()
        tab.Navigate(url)
        tab.WaitForDocumentReadyStateToBeComplete()
        tab.WaitForJavaScriptCondition(
            "document.hasOwnProperty('out') == true", timeout=60)

    def run_once(self):
        """Runs the test once."""
        # 1 for initial tab opened
        n_tabs = 1

        kills_monitor = MemoryKillsMonitor()
        last_event = ''
        # Open tabs until a tab discard notification or OOM arrives.
        with chrome.Chrome(init_network_controller=True) as cr:
            cr.browser.platform.SetHTTPServerDirectories(self.bindir)
            while last_event == '':
                self.create_alloc_page(cr, 800)
                time.sleep(3)
                n_tabs += 1
                last_event = kills_monitor.check_event()

        # Test is successful if at least one Chrome tab is killed by tab
        # discarder before kernel OOM killer invoked.
        if last_event == 'OOM_KILL':
            raise error.TestFail('OOM Kill happends before a tab is killed')

        result_title = 'NumberOfTabsAtFirstDiscard'
        self.write_perf_keyval({result_title : n_tabs})
        self.output_perf_value(description=result_title, value=n_tabs,
                               higher_is_better=True)

