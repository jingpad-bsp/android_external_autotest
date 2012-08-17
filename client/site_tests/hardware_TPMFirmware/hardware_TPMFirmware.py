# Copyright (c) 2010 The Chromium OS Authors. All rights reserved.
# Use of this source code is governed by a BSD-style license that can be
# found in the LICENSE file.

import logging, os, re, sys, shutil
from autotest_lib.client.bin import test, utils

class hardware_TPMFirmware(test.test):
    """
    Test of TPM functionality needed in firmware (client side of the test).
    See also server/site_tests/hardware_TPMFirmwareServer.
    """
    version = 1
    preserve_srcdir = True

    # Copies the TLCL test suite which is not installed by default on the test
    # image.
    def setup(self):
        sysroot = os.environ.get('SYSROOT', '/')
        bin_path = os.path.join(sysroot, 'usr/bin')
        for f in os.listdir(bin_path):
            if re.match('tpmtest_.*', f):
                shutil.copy(os.path.join(bin_path, f), self.bindir)

    # Runs a command, logs the output, and returns the exit status.
    def tpm_run(self, cmd, ignore_status=False):
        output = utils.run(cmd, ignore_status=ignore_status)
        logging.info(output)
        self.job.set_state("client_status", output.exit_status)


    # Sets up the system (if it isn't already) to run the tpm binaries.  This
    # is mostly needed after a reboot.  We don't rely on the system booting in
    # any particular state.
    def tpm_setup(self, with_tcsd=False):
        utils.run('mknod /dev/tpm c 10 224', ignore_status=True)
        utils.run('mknod /dev/tpm0 c 10 224', ignore_status=True)
        utils.run('modprobe tpm_tis force=1 interrupts=0', ignore_status=True)

        if (with_tcsd):
            utils.run('start tcsd')
        else:
            # It will be a problem if upstart automatically restarts tcsd.
            utils.run('stop tcsd', ignore_status=True)


    def run_once(self, subtest='None'):
        logging.info("Running TPM firmware client subtest %s", subtest)
        if (subtest == 'setup'):
            self.tpm_setup()
            self.tpm_write_status(0)
        elif (subtest == 'takeownership'):
            self.tpm_setup(with_tcsd=True)
            own_cmd = '/usr/local/sbin/tpm_takeownership -y -z'
            self.tpm_run(own_cmd)
        else:
            self.tpm_setup()
            cmd = os.path.join(self.bindir, subtest)
            self.tpm_run(cmd, ignore_status=True)
