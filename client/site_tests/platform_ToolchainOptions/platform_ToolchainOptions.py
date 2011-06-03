# Copyright (c) 2011 The Chromium OS Authors. All rights reserved.
# Use of this source code is governed by a BSD-style license that can be
# found in the LICENSE file.

import os

import logging
from autotest_lib.client.bin import test, utils
from autotest_lib.client.common_lib import error
from optparse import OptionParser

class ToolchainOptionSet:
    def __init__(self, description, bad_files, whitelist_file):
        self.description = description
        self.bad_set = set(bad_files.splitlines())
        self.whitelist_set = set([])
        self.process_whitelist_with_private(whitelist_file)


    def process_whitelist_with_private(self, whitelist_file):
        whitelist_files = [whitelist_file]
        private_file = os.path.join(os.path.dirname(whitelist_file),
                                    "private_" +
                                    os.path.basename(whitelist_file))
        whitelist_files.append(private_file)
        self.process_whitelists(whitelist_files)


    def process_whitelist(self, whitelist_file):
        if not os.path.isfile(whitelist_file):
            self.whitelist_set = self.whitelist_set.union(set([]))
        else:
            f = open(whitelist_file)
            whitelist = f.read().splitlines()
            f.close()
            self.whitelist_set = self.whitelist_set.union(set(whitelist))
        self.filtered_set = self.bad_set.difference(self.whitelist_set)
        self.new_passes = self.whitelist_set.difference(self.bad_set)


    def process_whitelists(self, whitelist_files):
        for whitelist_file in whitelist_files:
            self.process_whitelist(whitelist_file)


    def get_fail_summary_message(self):
        m = "Test %s " % self.description
        m += "%d failures\n" % len(self.filtered_set)
        return m


    def get_fail_message(self):
        m = self.get_fail_summary_message()
        sorted_list = list(self.filtered_set)
        sorted_list.sort()
        m += "FAILED:\n%s\n\n" % "\n".join(sorted_list)
        return m


    def __str__(self):
        m = "Test %s " % self.description
        m += ("%d failures, %d in whitelist, %d in filtered, %d new passes " %
              (len(self.bad_set),
               len(self.whitelist_set),
               len(self.filtered_set),
               len(self.new_passes)))

        if len(self.filtered_set):
            sorted_list = list(self.filtered_set)
            sorted_list.sort()
            m += "FAILED:\n%s" % "\n".join(sorted_list)
        else:
            m += "PASSED!"

        if len(self.new_passes):
            sorted_list = list(self.new_passes)
            sorted_list.sort()
            m += ("\nNew passes (remove these from the whitelist):\n%s" %
                  "\n".join(sorted_list))
        logging.debug(m)
        return m


class platform_ToolchainOptions(test.test):
    version = 2

    def get_cmd(self, test_cmd, find_options=""):
        base_cmd = ("find '%s' -wholename %s -prune -o "
                    " -wholename /proc -prune -o "
                    " -wholename /dev -prune -o "
                    " -wholename /sys -prune -o "
                    " -wholename /mnt/stateful_partition -prune -o "
                    " -wholename /usr/local -prune -o "
                    # There are files in /home/chronos that cause false
                    # positives, and since that's noexec anyways, it should
                    # be skipped.
                    " -wholename '/home/chronos' -prune -o "
                    " %s "
                    " -type f -executable -exec "
                    "sh -c 'file {} | grep -q ELF && "
                    "(%s || echo {})' ';'")
        rootdir = "/"
        cmd = base_cmd % (rootdir, self.autodir, find_options, test_cmd)
        return cmd


    # http://build.chromium.org/mirror/chromiumos/mirror/distfiles/
    # binutils-2.19.1.tar.bz2
    def setup(self, tarball="binutils-2.19.1.tar.bz2"):
        # clean
        if os.path.exists(self.srcdir):
            utils.system("rm -rf %s" % self.srcdir)

        tarball = utils.unmap_url(self.bindir, tarball, self.tmpdir)
        utils.extract_tarball_to_dir(tarball, self.srcdir)

        os.chdir(self.srcdir)
        utils.system("patch -p1 < ../binutils-2.19-arm.patch");
        utils.configure()
        utils.make(extra="CFLAGS+=\"-w\"")


    def create_and_filter(self, description, cmd, whitelist_file):
        full_cmd = self.get_cmd(cmd)
        bad_files = utils.system_output(full_cmd)
        cso = ToolchainOptionSet(description, bad_files, whitelist_file)
        cso.process_whitelist_with_private(whitelist_file)
        return cso


    def run_once(self, rootdir="/", args=[]):
        """
        Do a find for all the ELF files on the system.
        For each one, test for compiler options that should have been used
        when compiling the file.

        For missing compiler options, print the files.
        """

        parser = OptionParser()
        parser.add_option('--hardfp',
                          dest='enable_hardfp',
                          default=False,
                          action='store_true',
                          help='Whether to check for hardfp binaries.')
        (options, args) = parser.parse_args(args)

        option_sets = []

        libc_glob = "/lib/libc-[0-9]*"
        os.chdir(self.srcdir)

        # arm arch doesn't have hardened.
        if utils.get_cpu_arch() != "arm":
            fstack_cmd = ("binutils/objdump -CR {} 2>&1 | "
                          "egrep -q \"(stack_chk|Invalid|not recognized)\"")
            fstack_find_options = ((" -wholename '%s' -prune -o "
                                    # gconv locale .so's don't count:
                                    " -wholename '/usr/lib/gconv/*' -prune -o")
                                   % libc_glob)
            full_cmd = self.get_cmd(fstack_cmd, fstack_find_options)
            fstack_badfiles = utils.system_output(full_cmd)

            # special case check for libc, needs different objdump flags
            cmd = "binutils/objdump -D %s | egrep -q stack_chk || echo %s"
            fstack_libc_badfiles = utils.system_output(cmd % (libc_glob,
                                                              libc_glob))

            fstack_all_badfiles = ("%s\n%s" %
                                   (fstack_badfiles, fstack_libc_badfiles))
            fstack_whitelist = os.path.join(self.bindir, "fstack_whitelist")
            cos = ToolchainOptionSet("-fstack-protector-all",
                                     fstack_all_badfiles,
                                     fstack_whitelist)
            option_sets.append(cos)

            fortify_cmd = ("binutils/readelf -s {} 2>&1 | "
                           "egrep -q \"__.*_chk\"")
            fortify_whitelist = os.path.join(self.bindir, "fortify_whitelist")
            option_sets.append(self.create_and_filter("-D_FORTIFY_SOURCE=2",
                                                      fortify_cmd,
                                                      fortify_whitelist))

            now_cmd = ("binutils/readelf -d {} 2>&1 | "
                       "egrep -q \"BIND_NOW\"")
            now_whitelist = os.path.join(self.bindir, "now_whitelist")
            option_sets.append(self.create_and_filter("-Wl,-z,now",
                                                      now_cmd,
                                                      now_whitelist))
            relro_cmd = ("binutils/readelf -l {} 2>&1 | "
                         "egrep -q \"GNU_RELRO\"")
            relro_whitelist = os.path.join(self.bindir, "relro_whitelist")
            option_sets.append(self.create_and_filter("-Wl,-z,relro",
                                                      relro_cmd,
                                                      relro_whitelist))

            pie_cmd = ("binutils/readelf -l {} 2>&1 | "
                   "egrep -q \"Elf file type is DYN\"")
            pie_whitelist = os.path.join(self.bindir, "pie_whitelist")
            option_sets.append(self.create_and_filter("-fPIE",
                                                      pie_cmd,
                                                      pie_whitelist))

        if options.enable_hardfp and utils.get_cpu_arch() == 'arm':
            hardfp_cmd = ("binutils/readelf -A {} 2>&1 | "
                          "egrep -q \"Tag_ABI_VFP_args: VFP registers\"")
            hardfp_whitelist = os.path.join(self.bindir, "hardfp_whitelist")
            option_sets.append(self.create_and_filter("hardfp", hardfp_cmd,
                                                      hardfp_whitelist))

        fail_msg = ""
        fail_summary_msg = ""
        full_msg = "Test results:"
        num_fails = 0
        for cos in option_sets:
            if len(cos.filtered_set):
                num_fails += 1
                fail_msg += cos.get_fail_message() + "\n"
                fail_summary_msg += cos.get_fail_summary_message() + "\n"
            full_msg += str(cos) + "\n\n"

        logging.error(fail_msg)
        logging.debug(full_msg)
        if num_fails:
            raise error.TestFail(fail_summary_msg)

