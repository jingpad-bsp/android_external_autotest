# Copyright (c) 2011 The Chromium OS Authors. All rights reserved.
# Use of this source code is governed by a BSD-style license that can be
# found in the LICENSE file.

import logging
import os

from autotest_lib.client.bin import test, utils
from autotest_lib.client.common_lib import error

class security_BundledCRXs(test.test):
    version = 1
    _CRX_DIR = '/opt/google/chrome/extensions/'


    def load_baseline(self):
        """
        Return a list of crx's we expect, e.g.
        ['aciahcmjmecflokailenpkdchphgkefd.crx',
         'blpcfgokakmgnkcojhhkbfbldkacnbeo.crx', ...]
        """
        # Figure out path to baseline file, by looking up our own path
        bpath = os.path.abspath(__file__)
        bpath = os.path.join(os.path.dirname(bpath), 'baseline')
        bfile = open(bpath)
        baseline_data = bfile.read()
        baseline_set = set(baseline_data.splitlines())
        bfile.close()
        return baseline_set


    def fetch_bundled_crxs(self):
        """
        Return a list of crx's found bundled on the system.
        (The data returned is comparable to that of load_baseline().)
        """
        cmd = "find '%s' -xdev -name '*.crx' -printf '%%f\\n'"
        return set(utils.system_output(cmd % self._CRX_DIR).splitlines())


    def run_once(self):
        """
        Enumerate all the bundled CRXs.
        Fail if it does not match the expected set.
        """
        observed_set = self.fetch_bundled_crxs()
        baseline_set = self.load_baseline()

        # If something in the observed set is not
        # covered by the baseline...
        diff = observed_set.difference(baseline_set)
        if len(diff) > 0:
            for crx in diff:
                logging.error('New/unexpected bundled crx %s' % crx)

        # Or, things in baseline are missing from the system:
        diff2 = baseline_set.difference(observed_set)
        if len(diff2) > 0:
            for crx in diff2:
                logging.error('Missing bundled crx %s' % crx)

        if (len(diff) + len(diff2)) > 0:
            raise error.TestFail('Baseline mismatch')
