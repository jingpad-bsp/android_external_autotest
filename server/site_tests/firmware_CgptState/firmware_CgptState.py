# Copyright (c) 2011 The Chromium OS Authors. All rights reserved.
# Use of this source code is governed by a BSD-style license that can be
# found in the LICENSE file.

import logging
import subprocess

from autotest_lib.server.cros.faft.firmware_test import FirmwareTest


class firmware_CgptState(FirmwareTest):
    """
    Servo based executing the CgptState test on client side.

    This test triggers the CgptState test on client side. In the client
    CgptState test, it set kernels A and B with different cgpt states
    (priority, tries, successful) and checks their boot results.

    The test items and logic are now handled in client. This FAFT test
    just handles the reboot logic.
    See /usr/local/sbin/firmware/saft/cgpt_state.py for more detail.
    """
    version = 1

    host = None
    not_finished = True

    def run_test_step(self):
        """Run the actual test steps."""
        # Show the client log messages in another thread.
        show_client_log = subprocess.Popen([
                'ssh -o StrictHostKeyChecking=no '
                '-o UserKnownHostsFile=/dev/null root@%s '
                'tail -f /tmp/faft_log.txt' % self.host.ip], shell=True)
        # Trigger the CgptState test logic on client side.
        # TODO(waihong): Move the test items and logic in FAFT.
        if self.faft_client.cgpt.run_test_loop():
            self.not_finished = False
        # Terminate the log-showing thread and prepare for reboot.
        if show_client_log and show_client_log.poll() is None:
            show_client_log.terminate()

    def initialize(self, host, cmdline_args):
        super(firmware_CgptState, self).initialize(host, cmdline_args)
        self.host = host
        self.backup_cgpt_attributes()
        self.setup_dev_mode(dev_mode=False)
        self.setup_usbkey(usbkey=False)
        self.setup_kernel('a')

    def cleanup(self):
        self.restore_cgpt_attributes()
        super(firmware_CgptState, self).cleanup()

    def run_once(self):
        self.faft_client.cgpt.set_test_step(0)
        while self.not_finished:
            logging.info('======== Running CgptState test step %d ========',
                         self.faft_client.cgpt.get_test_step() + 1)
            self.run_test_step()
            self.reboot_warm()
