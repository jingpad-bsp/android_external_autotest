# Copyright (c) 2013 The Chromium OS Authors. All rights reserved.
# Use of this source code is governed by a BSD-style license that can be
# found in the LICENSE file.

import os

from telemetry.core import browser_finder, browser_options, exceptions
from telemetry.core import extension_to_load, util


# Name of the logged-in user specified by the telemetry login extension.
LOGIN_USER = 'test@test.test'


class Chrome(object):
    """Wrapper for creating a telemetry browser instance with extensions."""


    BROWSER_TYPE_LOGIN = 'system'
    BROWSER_TYPE_GUEST = 'system-guest'


    def __init__(self, logged_in=True, extension_paths=[]):
        finder_options = browser_options.BrowserFinderOptions()
        self._browser_type = (self.BROWSER_TYPE_LOGIN
                if logged_in else self.BROWSER_TYPE_GUEST)
        finder_options.browser_type = self._browser_type

        if logged_in:
            for path in extension_paths:
                extension = extension_to_load.ExtensionToLoad(
                        path, self._browser_type, is_component=True)
                finder_options.extensions_to_load.append(extension)
            self._extensions_to_load = finder_options.extensions_to_load

        finder_options.CreateParser().parse_args(args=[])
        browser_to_create = browser_finder.FindBrowser(finder_options)
        self._browser = browser_to_create.Create()
        self._browser.Start()


    def __enter__(self):
        return self


    def __exit__(self, *args):
        self.browser.Close()


    @property
    def browser(self):
        """Returns a telemetry browser instance."""
        return self._browser


    def get_extension(self, extension_path):
        """Fetches a telemetry extension instance given the extension path."""
        for ext in self._extensions_to_load:
            if extension_path == ext.path:
                return self.browser.extensions[ext]
        return None


    @property
    def browser_type(self):
        """Returns the browser_type."""
        return self._browser_type


    def wait_for_browser_to_come_up(self):
        """Waits for the browser to come up."""
        def _BrowserReady(cr):
            try:
                tab = cr.browser.tabs.New()
            except (exceptions.BrowserGoneException,
                    exceptions.BrowserConnectionGoneException):
                return False
            tab.Close()
            return True
        util.WaitFor(lambda: _BrowserReady(self), poll_interval=1, timeout=10)


    def did_browser_crash(self, func):
        """Runs func, returns True if the browser crashed, False otherwise.

        @param func: function to run.

        """
        try:
            func()
        except (exceptions.BrowserGoneException,
                exceptions.BrowserConnectionGoneException):
            return True
        return False


    def is_logged_in(self):
        """Returns true iff logged in."""
        # TODO(achuith): Do this better.
        return os.path.exists('/var/run/state/logged-in')
