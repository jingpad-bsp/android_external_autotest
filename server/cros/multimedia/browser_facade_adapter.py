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


    def new_tab(self, url):
        """Opens a new tab and loads URL.

        @param url: The URL to load.

        """
        self._browser_proxy.new_tab(url)


    def close_tab(self, url):
        """Closes a previously opened tab.

        @param url: The URL loaded for this tab when it was created.

        """
        self._browser_proxy.close_tab(url)
