# Copyright (c) 2013 The Chromium OS Authors. All rights reserved.
# Use of this source code is governed by a BSD-style license that can be
# found in the LICENSE file.

import re

from autotest_lib.client.bin import test, utils
from autotest_lib.client.common_lib import error
from autotest_lib.client.common_lib.cros import chrome
from telemetry.core import exceptions

class security_SandboxStatus(test.test):
    """Verify sandbox status."""
    version = 1


    def _EvaluateJavaScript(self, js):
        '''Evaluates js, returns None if an exception was thrown.'''

        try:
            return self._tab.EvaluateJavaScript(js)
        except exceptions.EvaluateException:
            return None

    def _CheckAdequatelySandboxed(self):
        '''Check that chrome:///sandbox shows "You are adequately sandboxed."'''
        sandbox_good_js = "document.getElementsByTagName('p')[0].textContent"
        sandbox_good = utils.poll_for_condition(
                lambda: self._EvaluateJavaScript(sandbox_good_js),
                exception=error.TestError(
                       'Failed to evaluate in chrome://sandbox "%s"'
                        % sandbox_good_js),
                timeout=30)
        if not re.match('You are adequately sandboxed.', sandbox_good):
            raise error.TestFail('Could not find "You\'re adequately '
                                 'sandboxed." in chrome://sandbox')

    def _CheckGPUCell(self, cell, content, error_msg):
        '''Checks the content of the cells in the GPU sandbox row.'''

        gpu_js = ("document.getElementsByTagName('table')"
                  "[1].rows[1].cells[%d].textContent" % cell)
        try:
            res = utils.poll_for_condition(
                    lambda: self._EvaluateJavaScript(gpu_js),
                    timeout=30)
        except utils.TimeoutError:
            raise error.TestError('Failed to evaluate in chrome://gpu "%s"'
                                  % gpu_js)

        if res.find(content) == -1:
            raise error.TestFail(error_msg)

    def run_once(self):
        '''Open various sandbox-related pages and test that we are sandboxed.'''
        with chrome.Chrome() as cr:
            self._tab = cr.browser.tabs[0]
            self._tab.Navigate('chrome://sandbox')
            self._CheckAdequatelySandboxed()

            self._tab.Navigate('chrome://gpu')
            self._CheckGPUCell(0, 'Sandboxed',
                               'Could not locate "Sandboxed" row in table')
            self._CheckGPUCell(1, 'true', 'GPU not sandboxed')
