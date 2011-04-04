# Copyright (c) 2010 The Chromium OS Authors. All rights reserved.
# Use of this source code is governed by a BSD-style license that can be
# found in the LICENSE file.

import time
from autotest_lib.client.common_lib import global_config
from autotest_lib.client.common_lib.cros import autoupdater
from autotest_lib.server import autoserv_parser
from autotest_lib.server.hosts import base_classes


parser = autoserv_parser.autoserv_parser


class ChromiumOSHost(base_classes.Host):
    """ChromiumOSHost is a special subclass of SSHHost that supports
    additional install methods.
    """
    def __initialize(self, hostname, *args, **dargs):
        """
        Construct a ChromiumOSHost object

        Args:
             hostname: network hostname or address of remote machine
        """
        super(ChromiumOSHost, self)._initialize(hostname, *args, **dargs)


    def machine_install(self, update_url=None):
        # TODO(seano): Once front-end changes are in, Kill this entire
        # cmdline flag; It doesn't match the Autotest workflow.
        if parser.options.image:
            update_url=parser.options.image
        elif not update_url:
            return False
        updater = autoupdater.ChromiumOSUpdater(host=self,
                                                update_url=update_url)
        updater.run_update()
        # Updater has returned, successfully, reboot the host.
        self.reboot(timeout=60, wait=True)

        # sleep for 1 min till chromeos-setgoodkernel marks the current
        # partition as 'working'. This is the only way to commit a good update
        # on rootfs and prevent future rollback. Note this is only a temp
        # solution and a formal fix is under discussion.
        time.sleep(60)
        # then do another reboot
        self.reboot(timeout=60, wait=True)

        # Following the reboot, verify the correct version.
        updater.check_version()

        # Clean up any old autotest directories which may be lying around.
        for path in global_config.global_config.get_config_value(
                'AUTOSERV', 'client_autodir_paths', type=list):
            self.run('rm -rf ' + path)
