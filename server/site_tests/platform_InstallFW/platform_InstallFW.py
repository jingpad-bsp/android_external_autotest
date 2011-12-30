# Copyright (c) 2010 The Chromium OS Authors. All rights reserved.
# Use of this source code is governed by a BSD-style license that can be
# found in the LICENSE file.

import logging
from autotest_lib.server import test, autotest, utils

class platform_InstallFW(test.test):
    version = 1

    def run_once(self, host=None, bios_path=None, bios_name=None):
        if bios_path == "local":
            fw_dst = "/usr/sbin/chromeos-firmwareupdate"
            is_shellball = True
        else:
            fw_src = "%s/%s" % (bios_path, bios_name)
            # Determine the firmware file is a shellball or a raw binary.
            is_shellball = (utils.system_output("file %s" % fw_src).find(
                    "shell script") != -1)
            fw_dst = "/tmp/%s" % bios_name
            # Copy binary from server to client.
            host.send_file(fw_src, fw_dst)

        # Install bios on a client.
        if is_shellball:
            host.run("sudo /bin/sh %s --mode factory_install" % fw_dst)
        else:
            host.run("sudo /usr/sbin/flashrom -w %s" % fw_dst)

        # Reboot client after installing the binary.
        host.reboot()
        # Get the versions of binaries.
        bios_info = host.run("sudo mosys -k smbios info bios")
        logging.info("Firmware version info: %s" % bios_info)
