# Copyright (c) 2010 The Chromium OS Authors. All rights reserved.
# Use of this source code is governed by a BSD-style license that can be
# found in the LICENSE file.

import os

from autotest_lib.client.bin import test, utils

class factory_Wipe(test.test):
    version = 1

    def run_once(self):
      # Stub test to switch to boot from the release image,
      # and tag stateful partition to indicate wipe on reboot.
      os.chdir(self.srcdir)

      # Tag the current image to be wiped.
      utils.run('touch /mnt/stateful_partition/factory_install_reset')
      # Switch to the release image.
      utils.run('./switch_partitions.sh')
      # Time for reboot.
      utils.run('shutdown -r now')
