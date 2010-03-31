# Copyright (c) 2010 The Chromium OS Authors. All rights reserved.
# Use of this source code is governed by a BSD-style license that can be
# found in the LICENSE file.

import os

from autotest_lib.client.bin import test, utils
from autotest_lib.client.common_lib import error

class platform_StackProtector(test.test):
    version = 1

    # http://build.chromium.org/mirror/chromiumos/mirror/distfiles/
    # binutils-2.19.1.tar.bz2
    def setup(self, tarball="binutils-2.19.1.tar.bz2"):
        # clean
        if os.path.exists(self.srcdir):
            utils.system("rm -rf %s" % self.srcdir)

        tarball = utils.unmap_url(self.bindir, tarball, self.tmpdir)
        utils.extract_tarball_to_dir(tarball, self.srcdir)

        os.chdir(self.srcdir)
        utils.configure(extra="-disable-werror")
        utils.system("make")


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
        os.chdir(self.srcdir)
        cmd = ("find '%s' -wholename /proc -prune -o "
               " -wholename /dev -prune -o "
               " -wholename /sys -prune -o "
               " -wholename /home/autotest -prune -o "
               " -wholename /mnt/stateful_partition -prune -o "
               " -type f -size +511 -exec "
               "sh -c 'binutils/objdump -CR {} 2>&1 | "
               "egrep -q \"(stack_chk|Invalid|not recognized)\" || echo {}' ';'"
               )
        badfiles = utils.system_output(cmd % rootdir)
        if badfiles:
            raise error.TestFail("Missing -fstack-protector:\n" + badfiles)
