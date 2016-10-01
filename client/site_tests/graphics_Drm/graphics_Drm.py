# Copyright 2016 The Chromium OS Authors. All rights reserved.
# Use of this source code is governed by a BSD-style license that can be
# found in the LICENSE file.

from autotest_lib.client.bin import test
from autotest_lib.client.common_lib import utils
from autotest_lib.client.cros import service_stopper
from autotest_lib.client.cros.graphics import graphics_utils


class graphics_Drm(test.test):
    """Runs one of the drm-tests.
    """
    version = 1
    GSC = None
    _services = None

    def initialize(self):
        self.GSC = graphics_utils.GraphicsStateChecker()
        self._services = service_stopper.ServiceStopper(['ui'])

    def cleanup(self):
        if self.GSC:
            self.GSC.finalize()
        if self._services:
            self._services.restore_services()

    def run_once(self, cmd, stop_ui=True):
        if stop_ui:
            self._services.stop_services()
        utils.run(cmd,
                  stderr_is_expected=False,
                  stdout_tee=utils.TEE_TO_LOGS,
                  stderr_tee=utils.TEE_TO_LOGS)
