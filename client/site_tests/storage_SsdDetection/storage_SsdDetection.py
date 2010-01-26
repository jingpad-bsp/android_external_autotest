# Copyright (c) 2010 The Chromium OS Authors. All rights reserved.
# Use of this source code is governed by a BSD-style license that can be
# found in the LICENSE file.

import os
import re

from autotest_lib.client.bin import test, utils
from autotest_lib.client.common_lib import error

class storage_SsdDetection(test.test):
    version = 1

    def setup(self):
        self.job.setup_dep(['hdparm'])
        # create a empty srcdir to prevent the error that checks .version file
        if not os.path.exists(self.srcdir):
            utils.system('mkdir %s' % self.srcdir)


    def run_once(self):
        # TODO(ericli): need to find a general solution to install dep packages
        # when tests are pre-compiled, so setup() is not called from client any
        # more.
        dep = 'hdparm'
        dep_dir = os.path.join(self.autodir, 'deps', dep)
        self.job.install_pkg(dep, 'dep', dep_dir)

        cmdline = file('/proc/cmdline').read()
        match = re.search(r'root=([^ ]+)', cmdline)
        if not match:
            raise error.TestError('Unable to find the root partition')
        device = match.group(1)[:-1]

        path = self.autodir + '/deps/hdparm/sbin/'
        hdparm = utils.run(path + 'hdparm -I %s' % device)

        match = re.search(r'Nominal Media Rotation Rate: (.+)$',
                          hdparm.stdout, re.MULTILINE)
        if match and match.group(1):
            if match.group(1) != 'Solid State Device':
                raise error.TestFail('The main disk is not a SSD, '
                    'Rotation Rate: %s' % match.group(1))
        else:
            raise error.TestNAError(
                'Rotation Rate not reported from the device, '
                'unable to ensure it is a SSD')
