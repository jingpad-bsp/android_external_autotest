# Copyright (c) 2010 The Chromium OS Authors. All rights reserved.
# Use of this source code is governed by a BSD-style license that can be
# found in the LICENSE file.

import logging, os, re, shutil, time
from autotest_lib.client.bin import site_utils
from autotest_lib.client.common_lib import error
from autotest_lib.server import autotest, test

class network_3GLoadFirmware(test.test):
	version = 1

	def flimflam(self, prog):
		return '/usr/lib/flimflam/test/%s' % prog

	def modem_isup(self):
		result = self.client.run(self.flimflam('mm-status'))
		s = result.stdout
		return s.find('Modem /org/chromium/ModemManager/Gobi') != -1

	def wait_modem(self):
		timeout = 15
		site_utils.poll_for_condition(
		    lambda: self.modem_isup(),
		    error.TestError('Timed out waiting for modem'),
		    timeout=timeout)

	def force_reload(self):
		self.client.run('initctl stop udev')
		self.client.run(self.flimflam('mm-powercycle -a'))
		self.client.run('reboot')
		if not self.client.wait_down(timeout=30):
			error.TestFail("Reboot didn't.")
		if not self.client.wait_up(timeout=40):
			error.TestFail("Target didn't come back up.")

	def run_once(self, host=None):
		self.client = host
		self.wait_modem()
		self.force_reload()
		result = self.client.run('dmesg')
		for line in result.stdout.split('\n'):
			if line.find('QCUSBNet2k') != -1:
				return
		error.TestFail("Firmware didn't reload after boot.")
