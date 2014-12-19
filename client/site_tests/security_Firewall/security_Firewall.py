# Copyright (c) 2012 The Chromium OS Authors. All rights reserved.
# Use of this source code is governed by a BSD-style license that can be
# found in the LICENSE file.

import logging
import os

from autotest_lib.client.bin import test
from autotest_lib.client.common_lib import error
from autotest_lib.client.common_lib import utils
from autotest_lib.client.cros.networking import apmanager_helper
from autotest_lib.client.cros.tendo import privetd_helper


class security_Firewall(test.test):
    """Tests that rules in iptables match our expectations exactly."""
    version = 1


    def get_firewall_settings(self):
        ipt_rules = utils.system_output("iptables -S")
        return set([line.strip() for line in ipt_rules.splitlines()])


    def load_baseline(self, baseline_filename):
        """The baseline file lists the iptables rules that we expect.

        @param baseline_filename: string name of file containing relevant rules.

        """
        baseline_path = os.path.join(self.bindir, baseline_filename)
        with open(baseline_path) as f:
            return set([line.strip() for line in f.readlines()])


    def dump_iptables_rules(self, ipt_rules):
        """Store actual rules in results/ for future use.

        Leaves a list of iptables rules in the results dir
        so that we can update the baseline file if necessary.

        @param ipt_rules: list of string containing rules we found on the board.

        """
        outf = open(os.path.join(self.resultsdir, "iptables_rules"), 'w')
        for rule in ipt_rules:
            outf.write(rule + "\n")

        outf.close()


    def log_error_rules(self, rules, message):
        """Log a set of rules and the problem with those rules.

        @param rules: list of string containing rules we have issues with.
        @param message: string detailing what our problem with the rules is.

        """
        rules_str = ", ".join(["'%s'" % rule for rule in rules])
        logging.error("%s: %s", message, rules_str)


    def run_once(self):
        """Matches found and expected iptables rules.
        Fails both when rules are missing and when extra rules are found.
        """

        baseline = self.load_baseline('baseline')
        # TODO(wiley) Remove when we get per-board baselines (crbug.com/406013)
        if privetd_helper.privetd_is_installed():
            baseline.update(self.load_baseline('baseline.privet'))
        if apmanager_helper.apmanager_is_installed():
            baseline.update(self.load_baseline('baseline.apmanager'))
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
