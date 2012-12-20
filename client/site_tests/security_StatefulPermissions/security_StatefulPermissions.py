# Copyright (c) 2012 The Chromium OS Authors. All rights reserved.
# Use of this source code is governed by a BSD-style license that can be
# found in the LICENSE file.

import logging
import re

from autotest_lib.client.bin import test, utils
from autotest_lib.client.common_lib import error

class security_StatefulPermissions(test.test):
    version = 1
    _STATEFUL_ROOT = "/mnt/stateful_partition"

    # Note that chronos permissions in /home are covered in greater detail
    # by 'security_ProfilePermissions'.
    _masks_byuser = {"adm": [],
                     "avfs": [],
                     "bin": [],
                     "bluetooth": ["/encrypted/var/lib/bluetooth"],
                     "chaps": [],
                     "chronos": ["/encrypted/chronos",
                                 "/encrypted/var/cache/app_pack",
                                 "/encrypted/var/cache/echo",
                                 "/encrypted/var/cache/touch_trial/selection",
                                 "/encrypted/var/lib/cromo",
                                 "/encrypted/var/lib/timezone",
                                 # TODO(derat) power_manager crosbug.com/36510
                                 "/encrypted/var/lib/power_manager",
                                 "/encrypted/var/lib/Synaptics/chronos.1000",
                                 "/encrypted/var/lib/opencryptoki",
                                 "/encrypted/var/log/connectivity.log",
                                 "/encrypted/var/log/connectivity.bak",
                                 "/encrypted/var/log/window_manager",
                                 # TODO(derat) power_manager crosbug.com/36510
                                 "/encrypted/var/log/power_manager",
                                 "/encrypted/var/log/metrics",
                                 "/encrypted/var/log/chrome",
                                 "/encrypted/var/minidumps",
                                 "/home/user"],
                     "chronos-access": [],
                     "cras": [],
                     "cromo": [],
                     "cros-disks": [],
                     "daemon": [],
                     "debugd": [],
                     "dhcp": ["/encrypted/var/lib/dhcpcd"],
                     "halt": ["/home/root"],
                     "input": [],
                     "ipsec": [],
                     "lp": [],
                     "messagebus": [],
                     "mtp": [],
                     "news": [],
                     "nobody": [],
                     "ntfs-3g": [],
                     "ntp": [],
                     "openvpn": [],
                     "operator": ["/home/root"],
                     "polkituser": [],
                     "portage": [],
                     "power": ["/encrypted/var/lib/power_manager",
                               "/encrypted/var/log/power_manager"],
                     "pkcs11": [],
                     "proxystate": [],
                     "qdlservice": [],
                     "root": None,
                     "shutdown": ["/home/root"],
                     "sshd": [],
                     "sync": ["/home/root"],
                     "syslog": ["/encrypted/var/log"],
                     "tcpdump": [],
                     "tor": [],
                     "tpmd": [],
                     "tss": ["/var/lib/tpm"],
                     "uucp": [],
                     "wpa": [],
                    }

    def generate_find(self, user, prunelist):
        if prunelist is None:
            return "true" # return a no-op shell command, e.g. for root.

        # Cover-up crosbug.com/14947 by masking out uma-events in all tests
        # TODO(jimhebert) remove this when 14947 is resolved.
        prunelist.append("/encrypted/var/log/metrics/uma-events")

        # Cover-up autotest noise.
        prunelist.append("/dev_image")
        prunelist.append("/var_overlay")

        cmd = "find STATEFUL_ROOT"
        for p in prunelist:
            cmd += " -path STATEFUL_ROOT%s -prune -o " % p
        # Note that we don't "prune" all of /var/tmp's contents, just mask
        # the dir itself. Any contents are still interesting.
        cmd += " -path STATEFUL_ROOT/encrypted/var/tmp -o "
        cmd += " -writable -ls -o -user %s -ls 2>/dev/null" % user
        return cmd


    def expected_owners(self):
        """Returns the set of file/directory owners expected in stateful."""
        # In other words, this is basically the users mentioned in
        # tests_byuser, except for any expected to actually own zero files.
        exclusions = set(["nobody"])
        return set(self._masks_byuser.keys()).difference(exclusions)


    def observed_owners(self):
        """Returns the set of file/directory owners present in stateful."""
        # The -user 101 prune is covering crosbug.com/14929.
        # TODO(jimhebert) remove this when 14929 is resolved.
        cmd = ("find STATEFUL_ROOT "
               "-user 101 -prune -o "
               "-path STATEFUL_ROOT/dev_image -prune -o "
               "-printf '%u\\n' | sort -u")
        return set(self.subst_run(cmd).splitlines())


    def owners_lacking_testcoverage(self):
        """
        Determines the set of owners not covered by any of the
        per-owner tests implemented in this class. Returns
        a set of usernames (possibly the empty set).
        """
        return self.observed_owners().difference(self.expected_owners())


    def log_owned_files(self, owner):
        """
        Sends information about all files in the stateful partition
        owned by a given owner to the standard logging facility.
        """
        cmd = "find STATEFUL_ROOT -user %s -ls" % owner
        cmd_output = self.subst_run(cmd)
        logging.error(cmd_output)


    def subst_run(self, cmd, stateful_root=_STATEFUL_ROOT):
        cmd = cmd.replace("STATEFUL_ROOT", stateful_root)
        return utils.system_output(cmd, ignore_status=True)


    def run_once(self):
        """
        Accounts for the contents of the stateful partition
        piece-wise, inspecting the level of access which can
        be obtained by each of the privilege levels (usernames)
        utilized in CrOS.

        The autotest passes if each of the owner-specific sub-tests pass,
        and, if there are no files unaccounted for (ie, no unexpected
        file-owners for which we have no tests.)
        """
        testfail = False

        unexpected_owners = self.owners_lacking_testcoverage()
        if unexpected_owners:
            testfail = True
            for o in unexpected_owners:
                self.log_owned_files(o)

        # Now run the sub-tests.
        for user, mask in self._masks_byuser.items():
            cmd = self.generate_find(user, mask)

            # The 'EOF' below helps us distinguish 2 types of failures.
            # We have to use ignore_status=True because many of these
            # find-based tests will exit(nonzero) to signal that they
            # encountered inaccessible directories, which we expect by-design.
            # This creates ambiguity as to whether empty output means
            # the test ran, and passed, or the su failed. Including an
            # expected 'EOF' output disambiguates these cases.
            cmd = "su -s /bin/sh -c '%s;echo EOF' %s" % (cmd, user)
            cmd_output = self.subst_run(cmd)

            if not cmd_output:
                # we never got 'EOF', su failed
                testfail = True
                logging.error("su failed while attempting to run:")
                logging.error(cmd)
                logging.error("[Got %s]" % cmd_output)
            elif not re.search("^\s*EOF\s*$", cmd_output):
                # we got test failures before 'EOF'
                testfail = True
                logging.error("Test for '%s' found unexpected files:\n%s" %
                              (user,cmd_output))

        if testfail:
            raise error.TestFail("Unexpected files/perms in stateful")
