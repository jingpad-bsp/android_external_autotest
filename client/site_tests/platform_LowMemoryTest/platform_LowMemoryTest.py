# Copyright (c) 2018 The Chromium OS Authors. All rights reserved.
# Use of this source code is governed by a BSD-style license that can be
# found in the LICENSE file.

import logging
import os
import re
import time

from autotest_lib.client.bin import test
from autotest_lib.client.bin import utils
from autotest_lib.client.common_lib import error
from autotest_lib.client.common_lib.cros import chrome
from autotest_lib.client.cros import cros_logging
from autotest_lib.client.cros.input_playback import input_playback

class MemoryKillsMonitor:
    """A util class for reading kill events."""

    # The event status enum.
    NO_EVENT = 0
    OOM_KILLED = 1
    TAB_DISCARDED = 2

    _LOG_FILE = '/var/log/chrome/chrome'
    _PATTERN_DISCARD = re.compile(
        'tab_manager_delegate_chromeos.*:(\d+) Killed tab')
    _PATTERN_OOM = re.compile('Tab OOM-Killed Memory details:')

    def __init__(self):
        self._log_reader = cros_logging.ContinuousLogReader(self._LOG_FILE)

    def check_event(self):
        """Returns the event status since last invocation.

        Returns:
            OOM_KILLED if oom killer is invoked. TAB_DISCARDED if some tab
            is discarded and the oom killer is not invoked. NO_EVENT
            otherwise.
        """
        discard = False
        for line in self._log_reader.read_all_logs():
            matched = self._PATTERN_DISCARD.search(line)
            if matched:
                logging.info('Matched line %s', line)
                discard = True
            matched = self._PATTERN_OOM.search(line)
            if matched:
                logging.info('Matched line %s', line)
                return MemoryKillsMonitor.OOM_KILLED
        if discard:
            return MemoryKillsMonitor.TAB_DISCARDED
        return MemoryKillsMonitor.NO_EVENT


def create_pages_and_check_oom(create_page_func, bindir):
    """Common code to create pages and to check OOM.

    Args:
        create_page_func: function to create page, it takes 2 arguments,
            cr: chrome wrapper, bindir: path to the test directory.
        bindir: path to the test directory.
    Returns:
        Dictionary of test results.
    """
    # 1 for initial tab opened.
    n_tabs = 1

    kills_monitor = MemoryKillsMonitor()
    last_event = MemoryKillsMonitor.NO_EVENT
    # Open tabs until a tab discard notification or OOM arrives.
    # Checking the event status:
    # NO_EVENT: creates one more page.
    # OOM_KILLED: failed.
    # TAB_DISCARDED: passed.
    with chrome.Chrome(init_network_controller=True) as cr:
        cr.browser.platform.SetHTTPServerDirectories(bindir)
        while last_event == MemoryKillsMonitor.NO_EVENT:
            create_page_func(cr, bindir)
            time.sleep(3)
            n_tabs += 1
            last_event = kills_monitor.check_event()

    # Test is successful if at least one Chrome tab is killed by tab
    # discarder and the kernel OOM killer isn't invoked.
    if last_event == MemoryKillsMonitor.OOM_KILLED:
        raise error.TestFail('OOM Killer invoked')

    # TODO: reports the page loading time.
    return {'NumberOfTabsAtFirstDiscard': n_tabs}


def get_alloc_size_per_page():
    """Returns the default alloc size per page."""
    ALLOC_MB_PER_PAGE_DEFAULT = 800
    ALLOC_MB_PER_PAGE_SUB_2GB = 400
    GB_TO_BYTE = 1024 * 1024 * 1024
    KB_TO_BYTE = 1024

    alloc_mb_per_page = ALLOC_MB_PER_PAGE_DEFAULT
    # Allocate less memory per page for devices with 2GB or less memory.
    if utils.memtotal() * KB_TO_BYTE < 2 * GB_TO_BYTE:
        alloc_mb_per_page = ALLOC_MB_PER_PAGE_SUB_2GB
    return alloc_mb_per_page


def create_alloc_page(cr, page_name, size_mb, bindir):
    """The program in alloc.html allocates a large array with random data.

    Args:
        cr: chrome wrapper.
        size_mb: size of the allocated javascript array in the page.
        bindir: path to the test directory.
    Returns:
        The created tab.
    """
    url = cr.browser.platform.http_server.UrlOf(
        os.path.join(bindir, page_name))
    url += '?alloc=' + str(size_mb)
    tab = cr.browser.tabs.New()
    tab.Navigate(url)
    tab.WaitForDocumentReadyStateToBeComplete()
    tab.WaitForJavaScriptCondition(
        "document.hasOwnProperty('out') == true", timeout=60)
    return tab


def random_pages(bindir):
    """Creates pages with random javascript data and checks OOM.

    Args:
        bindir: path to the test directory.
    """
    def create_random_page(cr, bindir):
        """Creates a page with random javascript data."""
        create_alloc_page(cr, 'alloc.html', get_alloc_size_per_page(), bindir)

    return create_pages_and_check_oom(create_random_page, bindir)


def form_pages(bindir):
    """Creates pages with pending form data and checks OOM.

    Args:
        bindir: path to the test directory.
    """
    player = input_playback.InputPlayback()
    player.emulate(input_type='keyboard')
    player.find_connected_inputs()

    def create_form_page(cr, bindir):
        """Creates a page with pending form data."""
        tab = create_alloc_page(cr, 'form.html', get_alloc_size_per_page(),
                                bindir)
        # Presses tab to focus on the first interactive element.
        player.blocking_playback_of_default_file(input_type='keyboard',
                                                 filename='keyboard_tab')
        # Fills the form.
        player.blocking_playback_of_default_file(input_type='keyboard',
                                                 filename='keyboard_a')

    ret = create_pages_and_check_oom(create_form_page, bindir)
    player.close()
    return ret


class platform_LowMemoryTest(test.test):
    """Memory pressure test."""
    version = 1

    def run_once(self, flavor='random'):
        """Runs the test once."""
        if flavor == 'random':
            perf_results = random_pages(self.bindir)
        elif flavor == 'form':
            perf_results = form_pages(self.bindir)

        self.write_perf_keyval(perf_results)
        for result_key in perf_results:
            self.output_perf_value(description=result_key,
                                   value=perf_results[result_key],
                                   higher_is_better=True)

