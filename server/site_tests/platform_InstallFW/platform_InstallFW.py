# Copyright (c) 2010 The Chromium OS Authors. All rights reserved.
# Use of this source code is governed by a BSD-style license that can be
# found in the LICENSE file.

import logging
import os
from autotest_lib.server import test, autotest

class platform_InstallFW(test.test):
    version = 1

    def run_once(self, host=None, bios_path=None, bios_name=None):
      # Copy binary from server to client.
      host.send_file("%s/%s" % (bios_path, bios_name),
                     "/tmp/%s" % bios_name)
      # Install bios on a client.
      host.run("sudo /usr/sbin/flashrom -w /tmp/%s" % bios_name)
      # Reboot client after installing the binary.
      host.reboot()
      # Get the versions of binaries.
      bios_info = host.run("sudo mosys -k smbios info bios")
      logging.info("Firmware version info: %s" % bios_info)
