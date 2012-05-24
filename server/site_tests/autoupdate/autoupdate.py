# Copyright (c) 2011 The Chromium OS Authors. All rights reserved.
# Use of this source code is governed by a BSD-style license that can be
# found in the LICENSE file.

import logging
from autotest_lib.client.common_lib import error
from autotest_lib.server import test


class autoupdate(test.test):
    version = 1

    def run_once(self, update_url, host, local_devserver=False):
        try:
            host.machine_install(force_update=True, update_url=update_url,
                                 local_devserver=local_devserver)
        except error.InstallError, e:
            logging.error(e)
            raise error.TestFail(str(e))
