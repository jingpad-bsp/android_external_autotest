# Copyright (c) 2012 The Chromium OS Authors. All rights reserved.
# Use of this source code is governed by a BSD-style license that can be
# found in the LICENSE file.

import logging
import mox
import pexpect
import time

import dli

import rpm_controller


class TestSentryRPMController(mox.MoxTestBase):


    def setUp(self):
        super(TestSentryRPMController, self).setUp()
        self.ssh = self.mox.CreateMock(pexpect.spawn)
        self.rpm = rpm_controller.SentryRPMController('chromeos-rack1-host8',
                                                      self.ssh)


    def testSuccessfullyChangeOutlet(self):
        """Should return True if change was successful."""
        prompt = 'Switched CDU:'
        password = 'admn'
        dut_hostname = 'chromos-rack1-host8'
        new_state = 'ON'
        self.ssh.expect('Password:', timeout=60)
        self.ssh.sendline(password)
        self.ssh.expect(prompt, timeout=60)
        self.ssh.sendline('%s %s' % (new_state, dut_hostname))
        self.ssh.expect('Command successful', timeout=60)
        self.ssh.sendline('logout')
        self.mox.ReplayAll()
        self.assertTrue(self.rpm.queue_request(dut_hostname, new_state))
        self.mox.VerifyAll()


    def testUnsuccessfullyChangeOutlet(self):
        """Should return False if change was unsuccessful."""
        prompt = 'Switched CDU:'
        password = 'admn'
        dut_hostname = 'chromos-rack1-host8'
        new_state = 'ON'
        self.ssh.expect('Password:', timeout=60)
        self.ssh.sendline(password)
        self.ssh.expect(prompt, timeout=60)
        self.ssh.sendline('%s %s' % (new_state, dut_hostname))
        self.ssh.expect('Command successful',
                        timeout=60).AndRaise(pexpect.TIMEOUT('Timed Out'))
        self.ssh.sendline('logout')
        self.mox.ReplayAll()
        self.assertFalse(self.rpm.queue_request(dut_hostname, new_state))
        self.mox.VerifyAll()


class TestWebPoweredRPMController(mox.MoxTestBase):


    def setUp(self):
        super(TestWebPoweredRPMController, self).setUp()
        self.dli_ps = self.mox.CreateMock(dli.powerswitch)
        hostname = 'chromeos-rack8a-rpm1'
        self.web_rpm = rpm_controller.WebPoweredRPMController(hostname,
                                                              self.dli_ps)
        outlet = 8
        dut = 'chromeos-rack8a-host8'
        # Outlet statuses are in the format "u'ON'"
        initial_state = 'u\'ON\''
        self.test_status_list_initial = [[outlet, dut, initial_state]]


    def testSuccessfullyChangeOutlet(self):
        """Should return True if change was successful."""
        test_status_list_final = [[8,'chromeos-rack8a-host8','u\'OFF\'']]
        self.dli_ps.statuslist().AndReturn(self.test_status_list_initial)
        self.dli_ps.off(8)
        self.dli_ps.statuslist().AndReturn(test_status_list_final)
        self.mox.ReplayAll()
        self.assertTrue(self.web_rpm.queue_request('chromeos-rack8a-host8',
                                                   'OFF'))
        self.mox.VerifyAll()


    def testUnsuccessfullyChangeOutlet(self):
        """Should return False if Outlet State does not change."""
        test_status_list_final = [[8,'chromeos-rack8a-host8','u\'ON\'']]
        self.dli_ps.statuslist().AndReturn(self.test_status_list_initial)
        self.dli_ps.off(8)
        self.dli_ps.statuslist().AndReturn(test_status_list_final)
        self.mox.ReplayAll()
        self.assertFalse(self.web_rpm.queue_request('chromeos-rack8a-host8',
                                                    'OFF'))
        self.mox.VerifyAll()


    def testDutNotOnRPM(self):
        """Should return False if DUT hostname is not on the RPM device."""
        self.dli_ps.statuslist().AndReturn(self.test_status_list_initial)
        self.mox.ReplayAll()
        self.assertFalse(self.web_rpm.queue_request('chromeos-rack8a-host1',
                                                    'OFF'))
        self.mox.VerifyAll()


if __name__ == "__main__":
    unittest.main()
