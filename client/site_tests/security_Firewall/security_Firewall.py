# Copyright (c) 2012 The Chromium OS Authors. All rights reserved.
# Use of this source code is governed by a BSD-style license that can be
# found in the LICENSE file.

import logging
import os

from autotest_lib.client.bin import test
from autotest_lib.client.common_lib import error
from autotest_lib.client.common_lib import utils


class security_Firewall(test.test):
    version = 1


    def get_firewall_settings(self):
        ipt_rules = utils.system_output("iptables -S")
        return set([line.strip() for line in ipt_rules.splitlines()])


    def load_baseline(self):
        """The baseline file lists the iptables rules that we expect.
        """

        baseline_path = os.path.join(self.bindir, 'baseline')
        return set([line.strip() for line in open(baseline_path).readlines()])


    def dump_iptables_rules(self, ipt_rules):
        """Leaves a list of iptables rules in the results dir
        so that we can update the baseline file if necessary.
        """

        outf = open(os.path.join(self.resultsdir, "iptables_rules"), 'w')
        for rule in ipt_rules:
            outf.write(rule + "\n")

        outf.close()


    def log_error_rules(self, rules, message):
        rules_str = ", ".join(["'%s'" % rule for rule in rules])
        logging.error("%s: %s" % (message, rules_str))


    def run_once(self):
        """Matches found and expected iptables rules.
        Fails both when rules are missing and when extra rules are found.
        """

        baseline = self.load_baseline()
        current = self.get_firewall_settings()

        # Save to results dir
        self.dump_iptables_rules(current)

        missing_rules = baseline - current
        extra_rules = current - baseline

        failed = False
        if len(missing_rules) > 0:
            failed = True
            self.log_error_rules(missing_rules, "Missing iptables rules")

        if len(extra_rules) > 0:
            failed = True
            self.log_error_rules(extra_rules, "Extra iptables rules")

        if failed:
            raise error.TestFail("Mismatched iptables rules")
