# Copyright (c) 2012 The Chromium OS Authors. All rights reserved.
# Use of this source code is governed by a BSD-style license that can be
# found in the LICENSE file.

import logging, os
from autotest_lib.client.bin import test, utils
from autotest_lib.client.common_lib import error

class security_ModuleLocking(test.test):
    version = 1

    def _passed(self, msg):
        logging.info('ok: %s' % (msg))

    def _failed(self, msg):
        logging.error('FAIL: %s' % (msg))
        self._failures.append(msg)

    def _fatal(self, msg):
        logging.error('FATAL: %s' % (msg))
        raise error.TestError(msg)

    def check(self, boolean, msg, fatal=False):
        if boolean == True:
            self._passed(msg)
        else:
            msg = "could not satisfy '%s'" % (msg)
            if fatal:
                self._fatal(msg)
            else:
                self._failed(msg)

    def module_loaded(self, module):
        module = module.replace('-', '_')
        match = "%s " % (module)
        for line in open("/proc/modules"):
            if line.startswith(match):
                return True
        return False

    def rmmod(self, module):
        if self.module_loaded(module):
            utils.system("rmmod %s" % (module))

    def modprobe(self, module):
        if not self.module_loaded(module):
            utils.system("modprobe %s" % (module))

    def module_loads_outside_rootfs(self, module):
        # Start from a clean slate.
        self.rmmod(module)

        # Make sure we can load with standard mechanisms.
        self.modprobe(module)
        self.rmmod(module)

        # Load module directly with insmod from root filesystem.
        ko = utils.system_output("find /lib/modules -name '%s.ko'" % (module))
        utils.system("insmod %s" % (ko))
        self.rmmod(module)

        # Load module directly with insmod from /tmp.
        tmp = "/tmp/%s.ko" % (module)
        utils.system("cp %s %s" % (ko, tmp))
        rc = utils.system("insmod %s" % (tmp), ignore_status=True)

        # Clean up.
        self.rmmod(module)
        utils.system("rm %s" % (tmp))

        if rc == 0:
            return True
        return False

    def module_loads_old_api(self, module):
        # Start from a clean slate.
        self.rmmod(module)

        # Use --force-modversion to trigger the old API.
        rc = utils.system("modprobe --force-modversion %s" % (module),
                          ignore_status=True)

        # Clean up.
        self.rmmod(module)

        if rc == 0:
            return True
        return False

    def run_once(self):
        # Empty failure list means test passes.
        self._failures = []

        # Check that the sysctl is either missing or set to 1.
        sysctl = "/proc/sys/kernel/chromiumos/module_locking"
        if os.path.exists(sysctl):
            self.check(open(sysctl).read() == '1\n', "%s enabled" % (sysctl))

        # Check the enforced state is to deny non-rootfs module loads.
        module = "test_module"
        loaded = self.module_loads_outside_rootfs(module)
        self.check(loaded == False, "cannot load %s from /tmp" % (module))

        # Check old API fails when enforcement enabled.
        loaded = self.module_loads_old_api(module)
        self.check(loaded == False, "cannot load %s with old API" % (module))

        # If the sysctl exists, verify that it will disable the restriction.
        if os.path.exists(sysctl):
            # Disable restriction.
            open(sysctl, "w").write("0\n")
            self.check(open(sysctl).read() == '0\n', "%s disabled" % (sysctl))

            # Check enforcement is disabled.
            loaded = self.module_loads_outside_rootfs(module)
            self.check(loaded == True, "can load %s from /tmp" % (module))

            # Check old API works when enforcement disabled.
            loaded = self.module_loads_old_api(module)
            self.check(loaded == True, "can load %s with old API" % (module))

            # Clean up.
            open(sysctl, "w").write("1\n")
            self.check(open(sysctl).read() == '1\n', "%s enabled" % (sysctl))

        # Raise a failure if anything unexpected was seen.
        if len(self._failures):
            raise error.TestFail((", ".join(self._failures)))
