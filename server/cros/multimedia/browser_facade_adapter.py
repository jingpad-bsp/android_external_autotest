# Copyright 2015 The Chromium OS Authors. All rights reserved.
# Use of this source code is governed by a BSD-style license that can be
# found in the LICENSE file.

"""An adapter to remotely access the browser facade on DUT."""


class BrowserFacadeRemoteAdapter(object):
    """BrowserFacadeRemoteAdapter is an adapter to remotely control DUT browser.

    The Autotest host object representing the remote DUT, passed to this
    class on initialization, can be accessed from its _client property.

    """
    def __init__(self, remote_facade_proxy):
        """Construct an BrowserFacadeRemoteAdapter.

        @param remote_facade_proxy: RemoteFacadeProxy object.

        """
        self._proxy = remote_facade_proxy


    @property
    def _browser_proxy(self):
        """Gets the proxy to DUT browser facade.

        @return XML RPC proxy to DUT browser facade.

        """
        return self._proxy.browser


    def start_custom_chrome(self, kwargs):
        """Start a custom Chrome with given arguments.

        @param kwargs: A dict of keyword arguments passed to Chrome.
        """
        self._browser_proxy.start_custom_chrome(kwargs)


    def start_default_chrome(self, restart=False):
        """Start the default Chrome.

        @param restart: True to start Chrome without clearing previous state.
        """
        self._browser_proxy.start_default_chrome(restart)


    def new_tab(self, url):
        """Opens a new tab and loads URL.

        @param url: The URL to load.
        @return a str, the tab descriptor of the opened tab.

        """
        return self._browser_proxy.new_tab(url)


    def close_tab(self, tab_descriptor):
        """Closes a previously opened tab.

        @param tab_descriptor: Indicate which tab to be closed.

        """
        self._browser_proxy.close_tab(tab_descriptor)
