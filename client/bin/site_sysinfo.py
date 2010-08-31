import os, shutil, re

from autotest_lib.client.common_lib import utils
from autotest_lib.client.bin import base_sysinfo
from autotest_lib.client.bin import chromeos_constants


logfile = base_sysinfo.logfile
command = base_sysinfo.command


class site_sysinfo(base_sysinfo.base_sysinfo):
    def __init__(self, job_resultsdir):
        super(site_sysinfo, self).__init__(job_resultsdir)

        # add in some extra command logging
        self.test_loggables.add(command(
            "ls -l /boot", "boot_file_list"))
        self.test_loggables.add(logfile(chromeos_constants.UPDATE_ENGINE_LOG))


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
