# Copyright (c) 2013 The Chromium OS Authors. All rights reserved.
# Use of this source code is governed by a BSD-style license that can be
# found in the LICENSE file.

from autotest_lib.client.common_lib import error
from autotest_lib.client.common_lib.cros import chrome

from telemetry.core import exceptions
from telemetry.core import util

class ChromeNetworkingTestContext(object):
    """
    ChromeNetworkingTestContext handles creating a Chrome browser session and
    launching a set of Chrome extensions on it. It provides handles for
    telemetry extension objects, which can be used to inject JavaScript from
    autotest.

    Apart from user provided extensions, ChromeNetworkingTestContext always
    loads the default network testing extension 'network_test_ext' which
    provides some boilerplate around chrome.networkingPrivate calls.

    Example usage:

        context = ChromeNetworkingTestContext()
        context.setup()
        extension = context.network_test_extension()
        extension.EvaluateJavaScript('var foo = 1; return foo + 1;')
        context.teardown()

    ChromeNetworkingTestContext also supports the Python 'with' syntax for
    syntactic sugar.

    """

    NETWORK_TEST_EXTENSION_PATH = ('/usr/local/autotest/cros/cellular/'
                                   'chrome_testing/network_test_ext')
    NETWORK_TEST_EXT_READY_TIMEOUT = 10
    FIND_NETWORKS_TIMEOUT = 5

    # Network type strings used by chrome.networkingPrivate
    CHROME_NETWORK_TYPE_ETHERNET = 'Ethernet'
    CHROME_NETWORK_TYPE_WIFI = 'WiFi'
    CHROME_NETWORK_TYPE_BLUETOOTH = 'Bluetooth'
    CHROME_NETWORK_TYPE_CELLULAR = 'Cellular'
    CHROME_NETWORK_TYPE_VPN = 'VPN'
    CHROME_NETWORK_TYPE_ALL = 'All'

    def __init__(self, extensions=None):
        if extensions is None:
            extensions = []
        extensions.append(self.NETWORK_TEST_EXTENSION_PATH)
        self._extension_paths = extensions
        self._chrome = None

    def __enter__(self):
        self.setup()
        return self

    def __exit__(self, *args):
        self.teardown()

    def _create_browser(self):
        self._chrome = chrome.Chrome(logged_in=True,
                                     extension_paths=self._extension_paths)

        # TODO(armansito): This call won't be necessary once crbug.com/251913
        # gets fixed.
        self._ensure_network_test_extension_is_ready()

    def _ensure_network_test_extension_is_ready(self):
        # Wait until the network test extension has fully executed its
        # background script before attempting to run any JavaScript on it.
        # TODO(armansito): This method won't be necessary once crbug.com/251913
        # gets fixed.
        extension = self.network_test_extension
        try:
            def _check_chrome_testing_is_defined():
                try:
                    extension.EvaluateJavaScript('chromeTesting')
                    return True
                except exceptions.EvaluateException:
                    return False
            util.WaitFor(_check_chrome_testing_is_defined,
                         self.NETWORK_TEST_EXT_READY_TIMEOUT)
        except util.TimeoutException:
            raise error.TestFail(
                    'network_test_ext was not ready within timeout')

    def _get_extension(self, path):
        if self._chrome is None:
            raise error.TestFail('A browser session has not been setup.')
        extension = self._chrome.get_extension(path)
        if extension is None:
            raise error.TestFail('Failed to find loaded extension "%s"' % path)
        return extension

    def setup(self):
        """
        Initializes a ChromeOS browser session that loads the given extensions
        with private API priviliges.

        """
        self._create_browser()

    def teardown(self):
        """
        Closes the browser session.

        """
        if self._chrome:
            self._chrome.browser.Close()
            self._chrome = None

    @property
    def network_test_extension(self):
        """
        @return Handle to the cellular test Chrome extension instance.
        @raises error.TestFail if the browser has not been set up or if the
                extension cannot get acquired.

        """
        return self._get_extension(self.NETWORK_TEST_EXTENSION_PATH)

    def _wait_for_found_networks(self):
        extension = self.network_test_extension
        def _get_found_networks(extension):
            return extension.EvaluateJavaScript('chromeTesting.foundNetworks')
        try:
            util.WaitFor(lambda: _get_found_networks(extension) is not None,
                         self.FIND_NETWORKS_TIMEOUT)
        except util.TimeoutException:
            raise error.TestFail('Timed out waiting for a valid network list.')
        networks = _get_found_networks(extension)
        if type(networks) != list:
            raise error.TestFail(
                    'Expected a list, found "' + repr(networks) + '".')
        return networks

    def find_cellular_networks(self):
        """
        Queries the current cellular networks.

        @return A list containing the found cellular networks.

        """
        return self.find_networks(self.CHROME_NETWORK_TYPE_CELLULAR)

    def find_networks(self, network_type):
        """
        Queries the current networks of the queried type.

        @param network_type: One of CHROME_NETWORK_TYPE_* strings.

        @return A list containing the found cellular networks.

        """
        extension = self.network_test_extension
        extension.ExecuteJavaScript(
                'chromeTesting.findNetworks("' + network_type + '");')
        networks = self._wait_for_found_networks()
        return networks

