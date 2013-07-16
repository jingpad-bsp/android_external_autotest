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
_BROWSER_TYPE_LOGIN = 'system'
_BROWSER_TYPE_GUEST = 'system-guest'


def _get_browser(browser_type):
    options = browser_options.BrowserOptions()
    options.browser_type = browser_type
    browser_to_create = browser_finder.FindBrowser(options)
    return browser_to_create.Create()


def logged_in_browser():
    """Returns a logged in browser.

    Wrapping this within a Python with/as construct will take care of
    automatically logging into Chrome at the start and logging out of Chrome
    at the end, e.g.:

    with chrome.logged_in_browser() as browser:
        do_test()  # Will be logged in for this.
    # Logged out at this point.

    @return A Telemetry Browser object supporting context management.
    """
    return _get_browser(_BROWSER_TYPE_LOGIN)


def incognito_browser():
    """Returns an incognito browser."""
    return _get_browser(_BROWSER_TYPE_GUEST)
