# Copyright (c) 2010 The Chromium OS Authors. All rights reserved.
# Use of this source code is governed by a BSD-style license that can be
# found in the LICENSE file.

from autotest_lib.client.bin import boottool, utils
from autotest_lib.client.bin.job import base_client_job


LAST_BOOT_TAG = object()

class site_job(base_client_job):
    def __init__(self, *args, **kwargs):
        base_client_job.__init__(self, *args, **kwargs)


    def reboot(self, tag=LAST_BOOT_TAG):
        if tag == LAST_BOOT_TAG:
            tag = self.last_boot_tag
        else:
            self.last_boot_tag = tag

        self.reboot_setup()
        self.harness.run_reboot()

        # sync first, so that a sync during shutdown doesn't time out
        utils.system("sync; sync", ignore_status=True)

        utils.system("(sleep 5; reboot) </dev/null >/dev/null 2>&1 &")
        self.quit()


    def require_gcc(self):
        return False
