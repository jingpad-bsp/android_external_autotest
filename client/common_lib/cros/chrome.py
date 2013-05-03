# Copyright (c) 2013 The Chromium OS Authors. All rights reserved.
# Use of this source code is governed by a BSD-style license that can be
# found in the LICENSE file.

"""Telemetry-based Chrome automation functions."""

from telemetry.core import browser_finder, browser_options


# The following constant is the name of the logged-in user that is specified
# by the Telemetry chromeOS login extension
# (chromium/src/tools/telemetry/telemetry/core/chrome/chromeos_login_ext).
# The value here must match what is specified in that login extension.
LOGIN_USER = 'test@test.test'


def login():
    """Logs into Chrome.

    Wrapping this within a Python with/as construct will take care of
    automatically logging into Chrome at the start and logging out of Chrome
    at the end, e.g.:

    with chrome.login() as chrome_obj:
        do_test()  # Will be logged in for this.
    # Logged out at this point.

    @return A Telemetry Browser object supporting context management.
    """
    default_options = browser_options.BrowserOptions()
    default_options.browser_type = 'system'
    browser_to_create = browser_finder.FindBrowser(default_options)
    return browser_to_create.Create()
