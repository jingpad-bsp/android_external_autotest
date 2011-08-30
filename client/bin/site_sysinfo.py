# Copyright (c) 2011 The Chromium OS Authors. All rights reserved.
# Use of this source code is governed by a BSD-style license that can be
# found in the LICENSE file.

import os, shutil, re, logging

from autotest_lib.client.common_lib import utils
from autotest_lib.client.bin import base_sysinfo
from autotest_lib.client.cros import constants as chromeos_constants


logfile = base_sysinfo.logfile
command = base_sysinfo.command


class logdir(base_sysinfo.loggable):
    def __init__(self, directory):
        super(logdir, self).__init__(directory, log_in_keyval=False)
        self.dir = directory


    def __repr__(self):
        return "site_sysinfo.logdir(%r)" % self.dir


    def __eq__(self, other):
        if isinstance(other, logdir):
            return self.dir == other.dir
        elif isinstance(other, loggable):
            return False
        return NotImplemented


    def __ne__(self, other):
        result = self.__eq__(other)
        if result is NotImplemented:
            return result
        return not result


    def __hash__(self):
        return hash(self.dir)


    def run(self, log_dir):
        if os.path.exists(self.dir):
            parent_dir = os.path.dirname(self.dir)
            utils.system("mkdir -p %s%s" % (log_dir, parent_dir))
            utils.system("rsync -a --exclude=autoserv* %s %s%s" % 
                         (self.dir, log_dir, parent_dir))


class purgeable_logdir(logdir):
    def __init__(self, directory):
        super(purgeable_logdir, self).__init__(directory)


    def run(self, log_dir):
        super(purgeable_logdir, self).run(log_dir)

        if os.path.exists(self.dir):
            utils.system("rm -rf %s/*" % (self.dir))



class site_sysinfo(base_sysinfo.base_sysinfo):
    def __init__(self, job_resultsdir):
        super(site_sysinfo, self).__init__(job_resultsdir)

        # add in some extra command logging
        self.boot_loggables.add(command("ls -l /boot",
                                        "boot_file_list"))
        self.before_iteration_loggables.add(
            command("/opt/google/chrome/chrome --version", "chrome_version"))
        self.test_loggables.add(purgeable_logdir("/home/chronos/user/log"))
        self.test_loggables.add(logdir("/var/log"))
        # We only want to gather and purge crash reports after the client test
        # runs in case a client test is checking that a crash found at boot
        # (such as a kernel crash) is handled.
        self.after_iteration_loggables.add(purgeable_logdir("/home/chronos/user/crash"))
        self.after_iteration_loggables.add(purgeable_logdir("/var/spool/crash"))
        self.test_loggables.add(logfile("/home/chronos/.Google/"
                                        "Google Talk Plugin/gtbplugin.log"))
        self.test_loggables.add(purgeable_logdir("/var/spool/crash"))


    def log_test_keyvals(self, test_sysinfodir):
        keyval = super(site_sysinfo, self).log_test_keyvals(test_sysinfodir)

        lsb_lines = utils.system_output(
            "cat /etc/lsb-release",
            ignore_status=True).splitlines()
        lsb_dict = dict(item.split("=") for item in lsb_lines)

        for lsb_key in lsb_dict.keys():
            # Special handling for build number
            if lsb_key == "CHROMEOS_RELEASE_DESCRIPTION":
                keyval["CHROMEOS_BUILD"] = (
                    lsb_dict[lsb_key].rstrip(")").split(" ")[3])
            keyval[lsb_key] = lsb_dict[lsb_key]

        # return the updated keyvals
        return keyval
