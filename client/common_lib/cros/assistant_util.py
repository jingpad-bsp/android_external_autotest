# Copyright 2019 The Chromium OS Authors. All rights reserved.
# Use of this source code is governed by a BSD-style license that can be
# found in the LICENSE file.
#
# assistant_util.py is supposed to be called from chrome.py for Assistant
# specific logic.

from autotest_lib.client.common_lib import error
from autotest_lib.client.common_lib import utils
from telemetry.core import exceptions


def enable_assistant(autotest_ext):
    """Enables Google Assistant.

    @param autotest_ext private autotest extension.
    @raise error.TestFail if failed to start Assistant service within time.
    """
    if autotest_ext is None:
        raise error.TestFail('Could not start Assistant service because '
                             'autotest extension is not available.')

    try:
        autotest_ext.ExecuteJavaScript('''
            window.__assistant_ready = 0;
            chrome.autotestPrivate.setAssistantEnabled(true,
                10 * 1000 /* timeout_ms */,
                () => {
                    if (chrome.runtime.lastError) {
                      window.__assistant_ready = -1;
                      window.__assistant_error_msg =
                            chrome.runtime.lastError.message;
                    } else {
                      window.__assistant_ready = 1;
                    }
                });
        ''')
    except exceptions.EvaluateException as e:
        raise error.TestFail('Could not start Assistant "%s".' % e)

    ready = utils.poll_for_condition(
                lambda: autotest_ext.EvaluateJavaScript(
                    'window.__assistant_ready'),
                desc='Wait for the assistant running state to return.')

    if ready == -1:
        raise error.TestFail(
                autotest_ext.EvaluateJavaScript(
                        'window.__assistant_error_msg'))
