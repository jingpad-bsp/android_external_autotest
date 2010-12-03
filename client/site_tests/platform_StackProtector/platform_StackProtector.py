# Copyright (c) 2010 The Chromium OS Authors. All rights reserved.
# Use of this source code is governed by a BSD-style license that can be
# found in the LICENSE file.

import os

from autotest_lib.client.bin import test, utils
from autotest_lib.client.common_lib import error

class platform_StackProtector(test.test):
    version = 2

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
        utils.make()


    def run_once(self, rootdir="/"):
        """
        Do a find for all files on the system
        For each one, run objdump on them. We'll get either:
        * output containing stack_chk (good)
        * stderr containing 'not recognized' on e.g. shell scripts (ok)
        For those, the egrep -q exit(0)'s and there's no output.
        But, for files compiled without stack protector, the egrep will
        exit(1) and we'll note the name of those files.

        Check all current/future partitions unless known harmless (e.g. proc).
        Skip files < 512 bytes due to objdump false positive and test speed.
        """
        libc_glob = "/lib/libc-[0-9]*"
        os.chdir(self.srcdir)
        cmd = ("find '%s' -wholename /proc -prune -o "
               " -wholename /dev -prune -o "
               " -wholename /sys -prune -o "
               " -wholename /home/autotest -prune -o "
               " -wholename /usr/local/autotest -prune -o "
               " -wholename /mnt/stateful_partition -prune -o "
               # A couple of files known to be a false positive:
               " -wholename '/home/chronos/Safe Browsing Bloom*' -prune -o "
               # libc needs to be checked differently, skip here:
               " -wholename '%s' -prune -o "
               " -wholename '/usr/lib/gconv/libCNS.so' -prune -o"
               " -type f -size +511 -exec "
               "sh -c 'binutils/objdump -CR {} 2>&1 | "
               "egrep -q \"(stack_chk|Invalid|not recognized)\" || echo {}' ';'"
               )
        badfiles = utils.system_output(cmd % (rootdir, libc_glob))

        # special case check for libc, needs different objdump flags
        cmd = "binutils/objdump -D %s | egrep -q stack_chk || echo %s"
        libc_stack_chk = utils.system_output(cmd % (libc_glob, libc_glob))

        if badfiles or libc_stack_chk:
            raise error.TestFail("Missing -fstack-protector:\n"
                                 + badfiles + libc_stack_chk)
