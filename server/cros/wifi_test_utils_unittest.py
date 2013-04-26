#!/usr/bin/python
#
# Copyright (c) 2013 The Chromium OS Authors. All rights reserved.
# Use of this source code is governed by a BSD-style license that can be
# found in the LICENSE file.

"""Unit tests for server/cros/wifi_test_utils.py."""

import unittest

from autotest_lib.server.cros import wifi_test_utils


class WiFiTestUtilsSimpleTest(unittest.TestCase):
    """Tests various methods in wifi_test_utils.py that require no mox."""


    HOST = 'chromeos1-row1-rack1-host1'


    def testGetMachineDomain_withHostnameNoDot(self):
        """Tests parsing of hostname with no embedded dot."""
        machine, domain = wifi_test_utils._get_machine_domain(self.HOST)
        self.assertEquals(self.HOST, machine)
        self.assertEquals('', domain)


    def testGetMachineDomain_withHostnameAndDot(self):
        """Tests parsing of hostname with embedded dot."""
        hostname = '.'.join([self.HOST, 'cros'])
        machine, domain = wifi_test_utils._get_machine_domain(hostname)
        self.assertEquals(self.HOST, machine)
        self.assertEquals('.cros', domain)


    def testGetServerAddrInLab_withHostNameNoDot(self):
        """Tests return of server hostname with no embedded dot."""
        expected = ''.join([self.HOST, '-server'])
        actual = wifi_test_utils.get_server_addr_in_lab(self.HOST)
        self.assertEquals(expected, actual)


    def testGetServerAddrInLab_withHostNameAndDot(self):
        """Tests return of server hostname with embedded dot."""
        hostname = '.'.join([self.HOST, 'cros'])
        expected = ''.join([self.HOST, '-server', '.cros'])
        actual = wifi_test_utils.get_server_addr_in_lab(hostname)
        self.assertEquals(expected, actual)


    def testGetRouterAddrInLab_withHostNameNoDot(self):
        """Tests return of router hostname with no embedded dot."""
        expected = ''.join([self.HOST, '-router'])
        actual = wifi_test_utils.get_router_addr_in_lab(self.HOST)
        self.assertEquals(expected, actual)


    def testGetRouterAddrInLab_withHostNameAndDot(self):
        """Tests return of router hostname with embedded dot."""
        hostname = '.'.join([self.HOST, 'cros'])
        expected = ''.join([self.HOST, '-router', '.cros'])
        actual = wifi_test_utils.get_router_addr_in_lab(hostname)
        self.assertEquals(expected, actual)


    def testGetAttenuatorAddrInLab_withHostNameNoDot(self):
        """Tests return of attenuator hostname with no embedded dot."""
        expected = ''.join([self.HOST, '-attenuator'])
        actual = wifi_test_utils.get_attenuator_addr_in_lab(self.HOST)
        self.assertEquals(expected, actual)


    def testGetAttenuatorAddrInLab_withHostNameAndDot(self):
        """Tests return of attenuator hostname with embedded dot."""
        hostname = '.'.join([self.HOST, 'cros'])
        expected = ''.join([self.HOST, '-attenuator', '.cros'])
        actual = wifi_test_utils.get_attenuator_addr_in_lab(hostname)
        self.assertEquals(expected, actual)

