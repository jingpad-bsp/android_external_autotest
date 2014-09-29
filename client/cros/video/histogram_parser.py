# Copyright (c) 2013 The Chromium OS Authors. All rights reserved.
# Use of this source code is governed by a BSD-style license that can be
# found in the LICENSE file.

import re
from collections import namedtuple

from autotest_lib.client.bin import utils
from autotest_lib.client.common_lib import error


BucketStats = namedtuple('BucketStats', 'value percent')


class HistogramParser(object):
    """
    Parses a chrome histogram page and provide access to its values.

    Example usage:
    parser = histogram_parser.HistogramParser('some_histogram_name')

    # Later access amazing magical values:
    buckets = parser.buckets

    if buckets and buckets[1] == ??:
        # do cool stuff

    """

    def __init__(self, chrome, histogram, time_out_s=10):
        """
        @param chrome: Chrome instance representing the browser in current test.
        @param histogram: string, name of the histogram of interest.
        @param time_out_s: int, max duration in secs to wait for specified
                           histogram to be loaded.

        """
        # This pattern was built by observing the chrome://histogram output
        self._histogram_pattern = ('Histogram.*([0-9]+)'
                                   'samples.*average.*([0-9]+\.[0-9]+)')

        self._bucket_pattern = '(^[0-9]+).*\(([0-9]+)'

        """
        Match counts are based on the text that needs to be parsed.
        E.g: "0   ---------------------------O (9 = 16.4%)" is a typical entry
        in the list of buckets. In this case we want to match 0 and 9,
        therefore the match count is 2.

        """

        self._histogram_match_count = 2
        self._bucket_match_count = 2

        self._histogram = histogram
        self._time_out_s = time_out_s
        self._raw_text = None
        self._sample_count = None
        self._average = None
        self._buckets = {}
        self.tab = chrome.browser.tabs.New()
        self.wait_for_histogram_loaded()
        self.parse()


    @property
    def buckets(self):
        """
        @returns the dictionary containing buckets and their values.

        """
        return self._buckets


    @property
    def sample_count(self):
        """
        @returns the count of all samples in histogram as int.

        """
        return self._sample_count


    @property
    def average(self):
        """
        @returns the average of bucket values as float.

        """
        return self._average


    def wait_for_histogram_loaded(self):
        """
        Uses js to poll doc content until valid content is retrieved.

        """
        def loaded():
            """
            Checks if the histogram page has been fully loaded.

            """

            self.tab.Navigate('chrome://histograms/%s' % self._histogram)
            self.tab.WaitForDocumentReadyStateToBeComplete()
            docEle = 'document.documentElement'
            self._raw_text = self.tab.EvaluateJavaScript(
                    "{0} && {0}.innerText".format(docEle))
            return self._histogram in self._raw_text

        msg = "%s not loaded. Waited %ss" % (self._histogram, self._time_out_s)

        utils.poll_for_condition(condition=loaded,
                                 exception=error.TestError(msg),
                                 sleep_interval=1)

    def parse(self):
        """
        Parses histogram text to retrieve useful properties.

        @raises whatever _check_match() raises.

        """

        histogram_entries = self._raw_text.split('\n')
        found_hist_title = False

        for entry in histogram_entries:
            matches = self._check_match(self._histogram_pattern,
                                        entry,
                                        self._histogram_match_count)

            if matches:
                if not found_hist_title:
                    self._sample_count = int(matches[0])
                    self._average = matches[1]
                    found_hist_title = True

                else:  # this is another histogram, bail out
                    return

            else:
                matches = self._check_match(self._bucket_pattern,
                                            entry,
                                            self._bucket_match_count)
                if matches:
                    self._buckets[int(matches[0])] = int(matches[1])

        bucket_sum = sum(self._buckets.values())

        for key, value in self._buckets.items():
            percent = (float(value) / bucket_sum) * 100
            percent = round(number=percent, ndigits=2)
            self._buckets[key] = BucketStats(value, percent)


    def _check_match(self, pattern, text, expected_match_count):
        """
        Checks if provided text contains a pattern and if so expected number of
        matches is found.

        @param pattern: string, regex pattern to search for.
        @param text: string, text to search for patterns.
        @param expected_match_count: int, number of matches expected.

        @returns: tuple, match groups, none if no match was found.
        @raises TestError if a match was found but number of matches is not
                          equal to expected count.

        """
        m = re.match(pattern, text)

        if not m:
            return m

        ln = len(m.groups())
        if ln != expected_match_count:
            msg = ('Expected %d matches. Got %d. Pattern: %s. Text: %s'
                   % (expected_match_count, ln, pattern, text))
            raise error.TestError(msg)

        return m.groups()


    def __str__(self):
        return ("Histogram name: %s. Buckets: %s"
                % (self._histogram, str(self._buckets)))