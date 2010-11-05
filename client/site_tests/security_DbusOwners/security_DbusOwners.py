# Copyright (c) 2010 The Chromium OS Authors. All rights reserved.
# Use of this source code is governed by a BSD-style license that can be
# found in the LICENSE file.

import logging
import os
import re
import sys
from xml.dom import minidom

from autotest_lib.client.bin import test, utils
from autotest_lib.client.common_lib import error

class security_DbusOwners(test.test):
    version = 1
    _DBUS_CONFIG_DIR = '/etc/dbus-1/system.d/'


    def load_baseline(self):
        """
        Return a list of interface names we expect to be owned
        by chronos.
        """
        # Figure out path to baseline file, by looking up our own path
        bpath = os.path.abspath(__file__)
        bpath = os.path.join(os.path.dirname(bpath), 'baseline')
        bfile = open(bpath)
        baseline_data = bfile.read()
        baseline_set = set(baseline_data.splitlines())
        bfile.close()
        return baseline_set


    def fetch_owners(self):
        """
        For every dbus interface XML, look for <policy user="chronos">
        sections containing <allow own="InterfaceName">. Return the
        list of interfaces owned by chronos
        """
        chronos_owned = []
        for root, dirs, files in os.walk(self._DBUS_CONFIG_DIR):
            for filename in files:
                # Skip cruft like dotfiles
                if not re.search('^[^.].*\.conf$', filename):
                    logging.debug('Skipping %s' % filename)
                    continue

                logging.debug('Parsing %s' % filename)
                xmldoc = minidom.parse(os.path.join(root,filename))
                policies = xmldoc.getElementsByTagName('policy')

                for policy in policies:
                    if (policy.hasAttribute('user') and
                        policy.getAttribute('user') == 'chronos'):
                        allows = policy.getElementsByTagName('allow')

                        for allow in allows:
                            if allow.hasAttribute('own'):
                                chronos_owned.append(allow.getAttribute('own'))
        return set(chronos_owned)


    def run_once(self):
        """
        Enumerate all the Dbus interfaces owned by chronos.
        Fail if it does not match the expected set.
        """
        observed_set = self.fetch_owners()
        baseline_set = self.load_baseline()

        # If something in the observed set is not
        # covered by the baseline...
        diff = observed_set.difference(baseline_set)
        if len(diff) > 0:
            for iface in diff:
                logging.error('New chronos-owned interface %s' % iface)

        # Or, things in baseline are missing from the system:
        diff2 = baseline_set.difference(observed_set)
        if len(diff2) > 0:
            for iface in diff2:
                logging.error('Missing chronos-owned interface %s' % iface)

        if (len(diff) + len(diff2)) > 0:
            raise error.TestFail('Baseline mismatch')
