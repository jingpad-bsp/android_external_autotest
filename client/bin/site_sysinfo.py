# Copyright (c) 2011 The Chromium OS Authors. All rights reserved.
# Use of this source code is governed by a BSD-style license that can be
# found in the LICENSE file.

import os

from autotest_lib.client.common_lib import utils, global_config
from autotest_lib.client.bin import base_sysinfo
from autotest_lib.client.cros import constants

get_value = global_config.global_config.get_config_value
collect_corefiles = get_value('CLIENT', 'collect_corefiles',
                              type=bool, default=True)


logfile = base_sysinfo.logfile
command = base_sysinfo.command


class logdir(base_sysinfo.loggable):
    """Represents a log directory."""
    def __init__(self, directory, additional_exclude=None):
        super(logdir, self).__init__(directory, log_in_keyval=False)
        self.dir = directory
        self.additional_exclude = additional_exclude


    def __repr__(self):
        return "site_sysinfo.logdir(%r, %s)" % (self.dir,
                                                self.additional_exclude)


    def __eq__(self, other):
        if isinstance(other, logdir):
            return (self.dir == other.dir and
                    self.additional_exclude == other.additional_exclude)
        elif isinstance(other, base_sysinfo.loggable):
            return False
        return NotImplemented


    def __ne__(self, other):
        result = self.__eq__(other)
        if result is NotImplemented:
            return result
        return not result


    def __hash__(self):
        return hash(self.dir) + hash(self.additional_exclude)


    def run(self, log_dir):
        """Copies this log directory to the specified directory.

        @param log_dir: The destination log directory.
        """
        if os.path.exists(self.dir):
            parent_dir = os.path.dirname(self.dir)
            utils.system("mkdir -p %s%s" % (log_dir, parent_dir))
            # Take source permissions and add ugo+r so files are accessible via
            # archive server.
            additional_exclude_str = ""
            if self.additional_exclude:
                additional_exclude_str = "--exclude=" + self.additional_exclude

            utils.system("rsync --no-perms --chmod=ugo+r -a --exclude=autoserv*"
                         " %s %s %s%s" % (additional_exclude_str, self.dir,
                                          log_dir, parent_dir))


class purgeable_logdir(logdir):
    """Represents a log directory that will be purged."""
    def __init__(self, directory, additional_exclude=None):
        super(purgeable_logdir, self).__init__(directory, additional_exclude)
        self.additional_exclude = additional_exclude

    def run(self, log_dir):
        """Copies this log dir to the destination dir, then purges the source.

        @param log_dir: The destination log directory.
        """
        super(purgeable_logdir, self).run(log_dir)

        if os.path.exists(self.dir):
            utils.system("rm -rf %s/*" % (self.dir))


class site_sysinfo(base_sysinfo.base_sysinfo):
    """Represents site system info."""
    def __init__(self, job_resultsdir):
        super(site_sysinfo, self).__init__(job_resultsdir)
        crash_exclude_string = None
        if not collect_corefiles:
            crash_exclude_string = "*.core"

        # add in some extra command logging
        self.boot_loggables.add(command("ls -l /boot",
                                        "boot_file_list"))
        self.before_iteration_loggables.add(
            command(constants.BROWSER_EXE + " --version", "chrome_version"))
        self.test_loggables.add(
            purgeable_logdir(
                os.path.join(constants.CRYPTOHOME_MOUNT_PT, "log")))
        self.test_loggables.add(logdir("/var/log"))
        # We only want to gather and purge crash reports after the client test
        # runs in case a client test is checking that a crash found at boot
        # (such as a kernel crash) is handled.
        self.after_iteration_loggables.add(
            purgeable_logdir(
                os.path.join(constants.CRYPTOHOME_MOUNT_PT, "crash"),
                additional_exclude=crash_exclude_string))
        self.after_iteration_loggables.add(
            purgeable_logdir(constants.CRASH_DIR,
                             additional_exclude=crash_exclude_string))
        self.test_loggables.add(
            logfile(os.path.join(constants.USER_DATA_DIR,
                                 ".Google/Google Talk Plugin/gtbplugin.log")))
        self.test_loggables.add(purgeable_logdir(
                constants.CRASH_DIR,
                additional_exclude=crash_exclude_string))
        # Collect files under /tmp/crash_reporter, which contain the procfs
        # copy of those crashed processes whose core file didn't get converted
        # into minidump. We need these additional files for post-mortem analysis
        # of the conversion failure.
        self.test_loggables.add(
            purgeable_logdir(constants.CRASH_REPORTER_RESIDUE_DIR))


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

        # get the hwid (hardware ID)
        keyval["hwid"] = utils.system_output('crossystem hwid')

        # return the updated keyvals
        return keyval
