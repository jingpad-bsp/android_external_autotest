# Copyright (c) 2011 The Chromium OS Authors. All rights reserved.
# Use of this source code is governed by a BSD-style license that can be
# found in the LICENSE file.

import logging
from autotest_lib.client.common_lib import error
from autotest_lib.server import test


class autoupdate(test.test):
    """Wrapper around host.machine_install for reinstalling a DUT."""
    version = 1

    def run_once(self, update_url, host, local_devserver=False, repair=False):
        """The method called by the control file to start the test.

        @param update_url: The url to use for updating the DUT.
        @param host: The host object to run machine_install on.
        @param local_devserver: If you want to use your own devserver for the
            install process. Default: False
        @param repair: If this install is to repair a broken machine.

        """
        try:
            host.machine_install(force_update=True, update_url=update_url,
                                 local_devserver=local_devserver, repair=repair)
        except error.InstallError, e:
            logging.error(e)
            raise error.TestFail(str(e))
