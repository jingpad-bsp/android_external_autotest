# Copyright 2015 The Chromium OS Authors. All rights reserved.
# Use of this source code is governed by a BSD-style license that can be
# found in the LICENSE file.

from autotest_lib.client.common_lib import error
from autotest_lib.server import test


_DEFAULT_MIN_VERSION = '3.10'


class brillo_KernelVersionTest(test.test):
    """Verify that a Brillo device runs a minimum kernel version."""
    version = 1

    def run_once(self, host=None, min_version=_DEFAULT_MIN_VERSION):
        try:
            result = host.run_output('uname -r').strip()
        except error.AutoservRunError:
            raise error.TestFail('Failed to check kernel version')

        for actual_comp, min_comp in zip(result.split('-')[0].split('.'),
                                         min_version.split('.')):
            if actual_comp < min_comp:
                raise error.TestFail(
                        'Device kernel version (%s) older than required (%s)' %
                        (result, min_version))
