# Copyright 2016 The Chromium OS Authors. All rights reserved.
# Use of this source code is governed by a BSD-style license that can be
# found in the LICENSE file.

from autotest_lib.client.bin import test
from autotest_lib.client.common_lib import error
from autotest_lib.client.common_lib import utils
from autotest_lib.client.cros import service_stopper
from autotest_lib.client.cros.graphics import graphics_utils


class graphics_Drm(test.test):
    """Runs one of the drm-tests.
    """
    version = 1
    GSC = None
    _services = None
    _timeout = 120

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
        try:
            result = utils.run(cmd,
                               timeout=self._timeout,
                               ignore_status=True,
                               stderr_is_expected=True,
                               verbose=True,
                               stdout_tee=utils.TEE_TO_LOGS,
                               stderr_tee=utils.TEE_TO_LOGS)
        except Exception:
            # Fail on exceptions.
            raise error.TestFail('Failed: Exception running %s' % cmd)

        # Fail on any stderr with first line of stderr for triage.
        if result.stderr:
            raise error.TestFail('Failed: %s (%s)' %
                                    (cmd, result.stderr.splitlines()[0]))

        # Fail on fishy output with said output for triage.
        stdout = result.stdout.lower()
        if 'fail' in stdout or 'error' in stdout:
            for line in result.stdout.splitlines():
                if 'fail' in line.lower() or 'error' in line.lower():
                    raise error.TestFail('Failed: %s (%s)' % (cmd, line))

        # Last but not least check return code and use it for triage.
        if result.exit_status != 0:
            raise error.TestFail('Failed: %s (exit=%d)' %
                                    (cmd, result.exit_status))
