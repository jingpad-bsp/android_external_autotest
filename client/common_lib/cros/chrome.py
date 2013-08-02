# Copyright (c) 2013 The Chromium OS Authors. All rights reserved.
# Use of this source code is governed by a BSD-style license that can be
# found in the LICENSE file.

from telemetry.core import browser_finder, browser_options, extension_to_load


# Name of the logged-in user specified by the telemetry login extension.
LOGIN_USER = 'test@test.test'


class Chrome(object):
    """Wrapper for creating a telemetry browser instance with extensions."""


    BROWSER_TYPE_LOGIN = 'system'
    BROWSER_TYPE_GUEST = 'system-guest'


    def __init__(self, logged_in=True, extension_paths=[]):
        options = browser_options.BrowserOptions()
        self._browser_type = (self.BROWSER_TYPE_LOGIN
                if logged_in else self.BROWSER_TYPE_GUEST)
        options.browser_type = self._browser_type

        if logged_in:
            for path in extension_paths:
                extension = extension_to_load.ExtensionToLoad(
                        path, self._browser_type, is_component=True)
                options.extensions_to_load.append(extension)
            self._extensions_to_load = options.extensions_to_load

        browser_to_create = browser_finder.FindBrowser(options)
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
