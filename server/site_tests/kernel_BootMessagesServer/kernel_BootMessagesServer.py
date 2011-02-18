# Copyright (c) 2011 The Chromium OS Authors. All rights reserved.
# Use of this source code is governed by a BSD-style license that can be
# found in the LICENSE file.

import logging, os

from autotest_lib.client.bin import utils
from autotest_lib.client.common_lib import error
from autotest_lib.server import test

_KERN_WARNING = 4

_WHITELIST = [
  "Kernel-defined memdesc doesn't match the one from EFI!",
  "Warning only 1919MB will be used.",
  "Use a HIGHMEM enabled kernel.",
  "pnp 00:01: io resource (0x164e-0x164f) overlaps 0000:00:1c.0 "
  "BAR 7 (0x1000-0x1fff), disabling",
  "i915 0000:00:02.0: Invalid ROM contents",
  "[drm:intel_init_bios] *ERROR* VBT signature missing",
  "usb 1-2: config 1 has an invalid interface number: 1 but max is 0",
  "usb 1-2: config 1 has no interface number 0",
  "device-mapper: verity: Failed to acquire device 'ROOT_DEV': -1",
  "device-mapper: table: 254:0: verity: Device lookup failed",
  "dm: starting dm-0 (vroot) failed",
  "EXT3-fs warning: maximal mount count reached, running e2fsck is "
  "recommended",
  "i2c i2c-2: The new_device interface is still experimental and may change "
  "in a near future",
  "industrialio: module is from the staging directory, "
  "the quality is unknown, you have been warned.",
  "tsl2563: module is from the staging directory, the quality is unknown, "
  "you have been warned.",
]

class kernel_BootMessagesServer(test.test):
  version = 1


  def read_dmesg(self, filename):
    f = open(filename, 'w')
    self.client.run('dmesg -r', stdout_tee=f)
    f.close()


  def reboot_machine(self):
    self.client.run('reboot')
    self.client.wait_down()
    self.client.wait_up()


  def run_once(self, host=None):
    self.client = host
    self.client_test = 'kernel_BootMessages'
    dmesg_filename = os.path.join(self.resultsdir, 'dmesg')

    self.reboot_machine()
    self.read_dmesg(dmesg_filename)
    dmesg = utils.read_file(dmesg_filename)
    unexpected = utils.check_raw_dmesg(dmesg, _KERN_WARNING, _WHITELIST)
    if unexpected:
      f = open(os.path.join(self.resultsdir, 'dmesg.err'), 'w')
      for line in unexpected:
          logging.error('UNEXPECTED DMESG: %s' % stripped_line)
          f.write('%s\n' % line)
      f.close()
      raise error.TestFail("Unexpected dmesg warnings and/or errors.")
