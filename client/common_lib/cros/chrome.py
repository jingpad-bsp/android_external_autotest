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


    def __init__(self, logged_in=True, extension_paths=[], autotest_ext=False):
        self._autotest_ext_path = None
        if autotest_ext:
            self._autotest_ext_path = os.path.join(os.path.dirname(__file__),
                                                   'autotest_private_ext')
            extension_paths.append(self._autotest_ext_path)

        finder_options = browser_options.BrowserFinderOptions()
        self._browser_type = (self.BROWSER_TYPE_LOGIN
                if logged_in else self.BROWSER_TYPE_GUEST)
        finder_options.browser_type = self.browser_type

        if logged_in:
            extensions_to_load = finder_options.extensions_to_load
            for path in extension_paths:
                extension = extension_to_load.ExtensionToLoad(
                        path, self.browser_type, is_component=True)
                extensions_to_load.append(extension)
            self._extensions_to_load = extensions_to_load

        finder_options.CreateParser().parse_args(args=[])
        b_options = finder_options.browser_options
        b_options.disable_component_extensions_with_background_pages = False
        b_options.create_browser_with_oobe = True

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
    def autotest_ext(self):
        """Returns the autotest extension."""
        return self.get_extension(self._autotest_ext_path)


    @property
    def login_status(self):
        """Returns login status."""
        ext = self.autotest_ext
        if not ext:
            return None

        ext.ExecuteJavaScript('''
            window.__login_status = null;
            chrome.autotestPrivate.loginStatus(function(s) {
              window.__login_status = s;
            });
        ''')
        return ext.EvaluateJavaScript('window.__login_status')


    @property
    def browser_type(self):
        """Returns the browser_type."""
        return self._browser_type


    def wait_for_browser_to_come_up(self):
        """Waits for the browser to come up. This should only be called after a
        browser crash.
        """
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

