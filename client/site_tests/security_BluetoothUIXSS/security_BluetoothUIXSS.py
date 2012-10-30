# Copyright (c) 2012 The Chromium OS Authors. All rights reserved.
# Use of this source code is governed by a BSD-style license that can be
# found in the LICENSE file.

import json
import logging

from autotest_lib.client.common_lib import error
from autotest_lib.client.cros import cros_ui_test

"""A test verifying that Chrome Bluetooth Settings UI isn't vulnerable to XSS

Uses PyAuto to execute JavaScript on the clients, using API calls to create
fake devices with malicious input and simulating user interaction to test
display implementation for vulnerabilities.
"""

class security_BluetoothUIXSS(cros_ui_test.UITest):
    version = 1

    # List of malicious strings to try as inputs to the UI.
    # Note that these strings must be escaped to be contained in JavaScript
    # double quote strings.
    _MALICIOUS_STRINGS = [
            '<SCRIPT>alert(1)</SCRIPT>',
            '>\'>\\"><SCRIPT>alert(1)</SCRIPT>',
            '<IMG SRC=\\"javascript:alert(1)\\">',
            ('<A HREF=\\"data:text/html;base64,'
                    'PHNjcmlwdD5hbGVydCgxKTwvc2NyaXB0Pgo=\\">...</A>'),
            '<div>',
            '<textarea>',
            '<style>',
            ('[0xC0][0xBC]SCRIPT[0xC0][0xBE]alert(1)[0xC0][0xBC]/SCRIPT[0xC0]'
                    '[0xBE]'),
            '+ADw-SCRIPT+AD4-alert(1)+ADw-/SCRIPT+AD4-',
            '&#<script>alert(1)</script>;',
            '<!-- Hello -- world > <SCRIPT>alert(1)</SCRIPT> -->',
            '<!<!-- Hello world > <SCRIPT>alert(1)</SCRIPT> -->',
            '\x3CSCRIPT\x3Ealert(1)\x3C/SCRIPT\x3E',
            '<IMG SRC=\\"j[0x00]avascript:alert(1)\\">',
            '<BASE HREF=\\"javascript:1;/**/\\"><IMG SRC=\\"alert(1)\\">',
            'javascript:alert(1);',
            ' xss_injection=\\"\\" ',
            '\\" xss_injection=\\"',
            '\' xss_injection=\'',
            '<!--',
            '\'',
            '\\"'
    ]

    # JavaScript helper function to determine the number of tag and text nodes
    # on a page.  Also looks for an injected attribute named "xss_injection".
    _NUMBER_OF_NODES_FUNC = """
            function numberOfNodesIn(currentNode) {
              if(currentNode.getAttribute && currentNode.getAttribute(
                  "xss_injection")) {
                var results = {
                    "effects_found":true,
                    "reason":"XSS attribute injection was successful"};
                window.domAutomationController.send(JSON.stringify(results));
                throw "XSS injection success";
              }
              var currentCount = currentNode.childNodes.length,
                  total = currentCount;
              for (var i = 0; i < currentCount; i++) total += numberOfNodesIn(
                  currentNode.childNodes[i]);
              return total;}
            """

    # JavaScript helper function to record the number of DOM nodes on a page
    # before and after calling a function to alter the DOM and compare the
    # difference result to an expected difference.
    _TEST_FOR_EFFECTS_FUNC = """
            function testForEffects(changeFunction, additionExpected) {
              var numberOfNodesBeforeAdding = numberOfNodesIn(document);
              changeFunction();
              var numberOfNodesAfterAdding = numberOfNodesIn(document);
              var reason = (numberOfNodesAfterAdding -
                  numberOfNodesBeforeAdding) + " new nodes found, " +
                  additionExpected + " expected.";
              var results = {
                  "effects_found":!(numberOfNodesAfterAdding ==
                  numberOfNodesBeforeAdding + additionExpected),
                  "count": (numberOfNodesAfterAdding-numberOfNodesBeforeAdding),
                  "reason":reason};
              return results;
            }
            """

    # The test needs to evaluate the impact to the DOM, of adding
    # certain malformed strings to the Bluetooth interface. To avoid
    # having a brittle connection to the current particular UI,
    # we avoid hardcoding these values. Instead, we can determine them
    # at runtime by sending a "nice" value through the test first,
    # and measuring the impact of that.
    _EXPECTED_DOM_IMPACT = None

    def init_expectations(self):
        self._EXPECTED_DOM_IMPACT = {}
        # A fake, but non-malicious, device name/address to use:
        fake = 'fake'
        # For add_bluetooth_device_to_list we need to baseline 2 cases,
        # 'unpaired' and 'paired'. It takes 2 calls to do this.
        self._EXPECTED_DOM_IMPACT['add'] = {'paired': 0, 'unpaired': 0}
        self.add_bluetooth_device_to_list(fake, fake, False, False, False, True)
        self.add_bluetooth_device_to_list(fake, fake, True, False, False, True)

        # For connect_bluetooth_device we need to baseline 2 cases,
        # 'clean' and 'unclean'. We can do this in 1 call.
        self._EXPECTED_DOM_IMPACT['connect'] = {'clean': 0, 'unclean': 0}
        self.connect_bluetooth_device(fake, fake, True, True, True, True)

    def add_bluetooth_device_to_list(self, name, address, paired, bonded,
            connected, self_calibrating=False):
        """Adds a fake Bluetooth device and checks for side effects.

        Uses JavaScript API calls to create a malicious fake Bluetooth device
        and counts the number of text/tag nodes on the web page to make sure
        that XSS wasn't successful.

        Args:
            name: String name of the fake device.
            address: String address of the fake device.
            paired: Boolean for whether or not device is already paired.
            bonded: Boolean for whether or not device is already bonded.
            connected: Boolean for whether or not device is already connected.
            self_calibrating: Boolean for whether the test is being run in a
                              self calibrating mode.

        Returns:
            A boolean representing whether or not XSS was successful.
        """
        if paired:
            expectations_key = 'paired'
        else:
            expectations_key = 'unpaired'
        expected_nodes = self._EXPECTED_DOM_IMPACT['add'][expectations_key]

        output = json.loads(self.pyauto.ExecuteJavascript("""
                %s
                %s
                function testAddToBluetoothList(name, address, paired, bonded,
                    connected, additionExpected) {
                  var addBluetoothDevice = function() {
                    options.BrowserOptions.addBluetoothDevice(
                        {"name":name, "address":address, "paired":paired,
                        "bonded":bonded, "connected":connected});
                  };
                  var results = testForEffects(addBluetoothDevice,
                      additionExpected);
                  options.BrowserOptions.removeBluetoothDevice(address);
                  window.domAutomationController.send(JSON.stringify(results));
                }
                testAddToBluetoothList("%s", "%s", %s, %s, %s, %d);
                """ % (self._NUMBER_OF_NODES_FUNC, self._TEST_FOR_EFFECTS_FUNC,
                name, address, str(paired).lower(), str(bonded).lower(),
                str(connected).lower(), expected_nodes)))

        if self_calibrating:
            logging.debug('Setting expectations for %s to %s' %
                          (expectations_key, output['count']))
            self._EXPECTED_DOM_IMPACT['add'][expectations_key] = output['count']

        side_effects_found = output['effects_found']

        if not side_effects_found:
            log_msg = '[PASS]'
        else:
            log_msg = '[FAIL]'
            self.pyauto.NavigateToURL('chrome://settings-frame/')

        logging.debug('%s Added device with name "%s", address "%s", paired:%s,'
                ' bonded:%s, connected:%s; %s' % (log_msg,
                name, address, paired, bonded, connected, output['reason']))

        return side_effects_found

    def add_bluetooth_devices_to_list(self, name, address):
        """Adds a fake Bluetooth device in all possible configurations.

        Calls add_bluetooth_device_to_list for each possible combination of
        paired, bonded, and connected flags for full coverage of a given name/
        address pair.

        Args:
            name: String name of the desired fake Bluetooth device.
            address: String address of the desired fake Bluetooth device.

        Returns:
            A boolean representing whether or not XSS was successful.
        """
        side_effects_found = self.add_bluetooth_device_to_list(name, address,
                False, False, False)
        side_effects_found = self.add_bluetooth_device_to_list(name, address,
                False, False, True) or side_effects_found
        side_effects_found = self.add_bluetooth_device_to_list(name, address,
                False, True, False) or side_effects_found
        side_effects_found = self.add_bluetooth_device_to_list(name, address,
                False, True, True) or side_effects_found
        side_effects_found = self.add_bluetooth_device_to_list(name, address,
                True, False, False) or side_effects_found
        side_effects_found = self.add_bluetooth_device_to_list(name, address,
                True, False, True) or side_effects_found
        side_effects_found = self.add_bluetooth_device_to_list(name, address,
                True, True, False) or side_effects_found
        side_effects_found = self.add_bluetooth_device_to_list(name, address,
                True, True, True) or side_effects_found
        return side_effects_found

    def test_adding(self):
        """Tests adding malicious Bluetooth devices.

        Calls add_bluetooth_devices_to_list() for all malicious strings.

        Returns:
            A boolean representing whether or not XSS is possible when
            adding a Bluetooth device.
        """
        self.pyauto.NavigateToURL('chrome://settings-frame/')

        side_effects_found = False
        for entry in self._MALICIOUS_STRINGS:
            side_effects_found = self.add_bluetooth_devices_to_list(entry,
                    entry) or side_effects_found
        return side_effects_found

    def connect_bluetooth_device(self, name, address, paired, bonded,
            connected, self_calibrating=False):
        """Connects a fake Bluetooth device and checks for side effects.

        Uses JavaScript UI API calls to simulate connecting to a fake Bluetooth
        device and counts the number of text/tag nodes on the web page to make
        sure that XSS wasn't successful.

        Args:
            name: String name of the fake device.
            address: String address of the fake device.
            paired: Boolean for whether or not device is already paired.
            bonded: Boolean for whether or not device is already bonded.
            connected: Boolean for whether or not device is already connected.
            self_calibrating: Boolean for whether the test is being run in
                              a self calibrating mode.

        Returns:
            A boolean representing whether or not XSS was successful.
        """
        # list of strings representing Bluetooth pairing states
        _PAIRING_STATES = ['bluetoothStartConnecting',
                'bluetoothEnterPinCode', 'bluetoothEnterPasskey',
                'bluetoothRemotePinCode', 'bluetoothRemotePasskey',
                'bluetoothConfirmPasskey']

        self.pyauto.NavigateToURL('chrome://settings-frame/')

        is_clean = 'clean'
        side_effects_found = False
        for state in _PAIRING_STATES:
            new_nodes_expected = self._EXPECTED_DOM_IMPACT['connect'][is_clean]
            js = """
                %s
                %s
                function testConnectBluetoothDevice(name, address, paired,
                    bonded, connected, pairing, additionExpected) {
                  var device = {"name":name, "address":address, "paired":paired,
                      "bonded":bonded, "connected":connected,
                      "pairing":pairing};
                  var connectBluetoothDevice = function(device) {
                    return function() {
                      options.BluetoothPairing.showDialog(device);
                    };
                  };
                  device.pairing = pairing;
                  results = testForEffects(connectBluetoothDevice(device),
                      additionExpected);
                  if(results.effects_found) {
                    window.domAutomationController.send(JSON.stringify(
                        results));
                    return;
                  }
                  window.domAutomationController.send(JSON.stringify(results));
                }
                testConnectBluetoothDevice("%s", "%s", %s, %s, %s, "%s", %d);
                """ % (self._NUMBER_OF_NODES_FUNC, self._TEST_FOR_EFFECTS_FUNC,
                       name, address, str(paired).lower(), str(bonded).lower(),
                       str(connected).lower(), state, new_nodes_expected)
            output = json.loads(self.pyauto.ExecuteJavascript(js))

            if self_calibrating:
                logging.debug('Setting expectations for %s to %s' %
                              (is_clean, output['count']))
                self._EXPECTED_DOM_IMPACT['connect'][is_clean] = output['count']

            side_effects_found_now = output['effects_found']

            if not side_effects_found_now:
                log_msg = '[PASS]'
                is_clean = 'unclean'
            else:
                side_effects_found = True
                log_msg = '[FAIL]'
                self.pyauto.NavigateToURL('chrome://settings-frame/')
                is_clean = 'clean'

            logging.debug('%s Connected device at stage %s with name "%s", '
            'address "%s", paired:%s, bonded:%s, connected:%s; %s' % (log_msg,
                    state, name, address, paired, bonded, connected,
                    output['reason']))

        return side_effects_found

    def connect_bluetooth_devices(self, name, address):
        """Connects a Bluetooth device in all possible configurations.

        Calls connect_bluetooth_device for each normally possible combination
        of paired, bonded, and connected flags for full coverage of a given
        name/address pair.

        Args:
            name: String name of the desired fake Bluetooth device.
            address: String address of the desired fake Bluetooth device.

        Returns:
            A boolean representing whether or not XSS was successful.
        """
        side_effects_found = self.connect_bluetooth_device(name, address, False,
                False, False)
        side_effects_found = self.connect_bluetooth_device(name, address, False,
                True, False) or side_effects_found
        return side_effects_found

    def test_connecting(self):
        """Tests connecting to malicious Bluetooth devices.

        Calls connect_bluetooth_devices() for all malicious strings.

        Returns:
            A boolean representing whether or not XSS is possible when
            connecting to a Bluetooth device.
        """
        side_effects_found = False
        for entry in self._MALICIOUS_STRINGS:
            side_effects_found = self.connect_bluetooth_devices(entry,
                    entry) or side_effects_found
        return side_effects_found

    def set_up(self):
        """Sets up environment for testing.

        Checks if Bluetooth was already turned on and turns it on if it wasn't
        on already.
        """
        self.pyauto.NavigateToURL('chrome://settings-frame/')
        setup_js = ('$("advanced-settings-expander").click();'
                'var bluetooth_was_enabled = $("enable-bluetooth").checked;'
                'if(!bluetooth_was_enabled) $("enable-bluetooth").click();'
                'var results = {"bluetooth_was_enabled":bluetooth_was_enabled};'
                'window.domAutomationController.send(JSON.stringify(results));')
        self.start_env = json.loads(self.pyauto.ExecuteJavascript(setup_js))

    def tear_down(self):
        """Tears down environment after testing.

        Disables Bluetooth if it was disabled before testing.
        """
        if not self.start_env['bluetooth_was_enabled']:
            self.pyauto.NavigateToURL('chrome://settings-frame/')
            teardown_js = ('$("advanced-settings-expander").click();'
                    '$("enable-bluetooth").click();'
                    'window.domAutomationController.send("")')
            self.pyauto.ExecuteJavascript(teardown_js)

    def run_once(self):
        """Main function.

        Runs all test helper functions.

        Raises:
            error.TestFail if XSS was successful in any test.
        """
        self.set_up()
        self.init_expectations()

        side_effects_found = self.test_adding()
        side_effects_found = self.test_connecting() or side_effects_found

        self.tear_down()

        if side_effects_found:
            raise error.TestFail('XSS vulnerabilities were found.')
