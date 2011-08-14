# Copyright (c) 2011 The Chromium OS Authors. All rights reserved.
# Use of this source code is governed by a BSD-style license that can be
# found in the LICENSE file.
import logging, random, re, sgmllib, threading, time, urllib

from autotest_lib.client.common_lib import error
from autotest_lib.server.cros import servo_test

SLEEP_DEFAULT_SEED = 1
SLEEP_DEFAULT_SECS = { 'on': {'min': 3, 'max': 6},
                       'off': {'min': 10, 'max': 15}}
SLEEP_FAST_SECS = { 'on': {'min': 1, 'max': 5},
                    'off': {'min': 1, 'max': 5}}
MAX_TABS = 10
# TODO(tbroch) investigate removing retries and instead querying network status
# to determine if its ok to try loading a new tab
MAX_TAB_RETRIES = 3


class AlexaParser(sgmllib.SGMLParser):
    """Class to parse Alexa html for popular websites.


    Attributes:
      sites: List of hyperlinks (URL) gathered from Alexa site
    """


    def __init__(self, verbose=0):
        sgmllib.SGMLParser.__init__(self, verbose)
        self._sites = []


    def start_a(self, attributes):
        """Harvest URL's of top sites to visit later."""
        for name, value in attributes:
            if name == "href":
                match = re.search(".*/(.+)#keywords", value)
                if match:
                    self._sites.append("http://www." + match.group(1))


    def parse(self, html):
        """Parse the given html string."""
        self.feed(html)
        self.close()


    def get_sites(self):
        """Retrieve list of urls.

        Returns:
          List of urls
        """
        return self._sites


class AlexaSites(object):
    """Class to scrape list of URL's from Alexa ranking website.

    Attributes:
      url_prefix: string of URL prefix.  Used to assemble final Alexa URL to
        visit and scrape for top sites
      url_suffix: string of URL suffix.  Another component of final URL
      parser: SGMLParser instance object to
      num_sites: number of top ranked sites to scrape
    """


    def __init__(self, url_prefix, url_suffix, num_sites):
        self._url_prefix = url_prefix
        self._url_suffix = url_suffix
        self._parser = AlexaParser()
        self._num_sites = num_sites


    def get_sites(self):
        """Generate list of sites and return.

        Returns:
          list of url strings
        """
        i = 0
        prev_sites = -1
        cur_sites = len(self._parser.get_sites())
        while cur_sites < self._num_sites and \
                cur_sites > prev_sites:
            fd = urllib.urlopen("%s%d%s" % (self._url_prefix, i,
                                            self._url_suffix))
            html = fd.read()
            fd.close()
            self._parser.parse(html)
            i += 1
            prev_sites = cur_sites
            cur_sites = len(self._parser.get_sites())
        return self._parser.get_sites()[0:self._num_sites]


class SurfThread(threading.Thread):
    """Class to surf to a list of URL's."""


    def __init__(self, pyauto, sites):
        threading.Thread.__init__(self)
        self._sites = sites
        self._pyauto = pyauto


    def run(self):
        for cnt, url in enumerate(self._sites):
            logging.info("site %d of %d is %s", cnt + 1, len(self._sites), url)
            retry = 0
            while not self._pyauto.AppendTab(url) and retry < MAX_TAB_RETRIES:
                retry += 1
                logging.info("retry %d of site %d", retry, url)
            if retry == MAX_TAB_RETRIES:
                raise error.TestFail("Unable to browse %s" % url)
            tab_count = self._pyauto.GetTabCount()
            logging.info("tab count is %d", tab_count)
            # avoid tab bloat
            # TODO(tbroch) investigate different tab closure methods
            if tab_count > MAX_TABS:
                self._pyauto.CloseBrowserWindow(0)


class LidThread(threading.Thread):
    """Class to continually open and close lid."""


    def __init__(self, server, num_cycles, sleep_seed=None, sleep_secs=None):
        threading.Thread.__init__(self)
        self._num_cycles = num_cycles
        self._server = server

        if not sleep_secs:
            sleep_secs = SLEEP_DEFAULT_SECS
        self._sleep_secs = sleep_secs

        if not sleep_seed:
            sleep_seed = SLEEP_DEFAULT_SEED
        self._sleep_seed = sleep_seed


    def run(self):
        robj = random.Random()
        robj.seed(self._sleep_seed)
        for i in xrange(1, self._num_cycles + 1):
            logging.info("Lid cycle %d of %d", i, self._num_cycles)
            self._server.servo.set_nocheck('lid_open', 'no')
            time.sleep(robj.uniform(self._sleep_secs['on']['min'],
                                    self._sleep_secs['on']['max']))
            self._server.servo.set_nocheck('lid_open', 'yes')
            time.sleep(robj.uniform(self._sleep_secs['off']['min'],
                                    self._sleep_secs['off']['max']))


class platform_LidStress(servo_test.ServoTest):
    """Uses servo to repeatedly close & open lid while surfing."""
    version = 1


    def run_once(self, host, num_cycles=None):
        if not num_cycles:
            num_cycles = 50

        self.pyauto.LoginToDefaultAccount()

        # open & close lid frequently and quickly
        lid_fast = LidThread(self, num_cycles, None, SLEEP_FAST_SECS)
        lid_fast.start()
        tout = SLEEP_FAST_SECS['on']['max'] + SLEEP_FAST_SECS['off']['max']
        lid_fast.join(timeout=num_cycles * tout)

        # surf & open & close lid less frequently
        alexa = AlexaSites("http://www.alexa.com/topsites/countries;",
                           "/US", num_cycles)
        surf = SurfThread(self.pyauto, alexa.get_sites())
        lid = LidThread(self, num_cycles)

        surf.start()
        lid.start()

        tout = SLEEP_DEFAULT_SECS['on']['max'] + \
            SLEEP_DEFAULT_SECS['off']['max']
        lid.join(timeout=num_cycles * tout)
        surf.join(timeout=num_cycles * tout)
