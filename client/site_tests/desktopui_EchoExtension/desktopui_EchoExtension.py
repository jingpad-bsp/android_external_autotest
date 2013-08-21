# Copyright (c) 2013 The Chromium OS Authors. All rights reserved.
# Use of this source code is governed by a BSD-style license that can be
# found in the LICENSE file.

from telemetry.core import util

from autotest_lib.client.bin import test
from autotest_lib.client.common_lib import error
from autotest_lib.client.common_lib.cros import chrome


_MOCK_ORIGIN_SUCCESS_JS = """
    echo.verifyOrigin = function(origin, requestNonce, successCallback,
                                 failureCallback) {
        successCallback();
    };
"""
_MOCK_CONSENT_DENY_JS = """
    echo.requestConsent = function(origin, serviceName, senderTabId,
                                   requestData, sendResponse) {
        setTimeout(function() {
                   echo.consentCallback(false, requestData,
                                        sendResponse);
                   }, 500);
    };
"""
_MOCK_CONSENT_ALLOW_JS = """
    echo.requestConsent = function(origin, serviceName, senderTabId,
                                   requestData, sendResponse) {
        setTimeout(function() {
                   echo.consentCallback(true, requestData,
                                        sendResponse);
                   }, 500);
    };
"""
_MAIN_URL = ('chrome-extension://kddnkjkcjddckihglkfcickdhbmao'
             'dcn/main.html')
_BROKER_URL = ('chrome-extension://kddnkjkcjddckihglkfcickdhbm'
               'aodcn/broker.html')
_NOT_ELIGIBLE_URL = ('chrome-extension://kddnkjkcjddckihglkfci'
                     'ckdhbmaodcn/not-eligible.html')
_MAIN_TAB_IDX = 1
_BROKER_TAB_IDX = 2
_NOT_ELIGIBLE_TAB_IDX = 3
_VERIFICATION_TIME_OUT = 15


class desktopui_EchoExtension(test.test):
    """Autotest for ECHO extension.

    This test sends different request to ECHO extension and checks that
    expected error messages are displayed.
    """

    version = 1


    def send_request(self):
        """Send check request to ECHO extension."""

        js_request = """
            chrome.extension.sendMessage({
                origin: document.location.href,
                serviceName: 'service',
                serviceId: 'serviceId',
                requestNonce: 'requestNonce'}, function() {});
        """

        broker_tab = self.browser.tabs[_BROKER_TAB_IDX]
        broker_tab.Activate()
        broker_tab.ExecuteJavaScript(js_request)


    def check_text_in_page(self, tab, text):
        """Check to see if the text is in a web page.

        @param tab: The current tab.
        @param text: The expected text to look for.
        """

        code = """
            (function() {
                function _findElement(element, text) {
                    if (element.innerText &&
                        element.innerText.search(text) >= 0) {
                        return element;
                    }
                    for (var i in element.childNodes) {
                        var found = _findElement(element.childNodes[i], text);
                        if (found)
                            return found;
                    }
                    return null;
                }
                var _element = _findElement(document, \"%s\");
                if (_element) {
                    return true;
                }
                return false;
            })();""" % text
        return tab.EvaluateJavaScript(code)


    def verify_message(self, key_string):
        """Verifies that the expected error message is displayed.

        @param key_string: The key_string needs to be verified.
        """

        def verify_message_condition():
            """The condition to verify the expected message is displayed."""

            display_tab = self.browser.tabs[_NOT_ELIGIBLE_TAB_IDX]
            display_tab.Navigate(_NOT_ELIGIBLE_URL)
            display_tab.Activate()
            js_code = """
                var msg = chrome.i18n.getMessage('%s');
                msg;
            """
            js_code = js_code % key_string
            expected_msg = display_tab.EvaluateJavaScript(js_code)
            expected_msg = expected_msg[0:expected_msg.index('.')]
            return self.check_text_in_page(display_tab, expected_msg)

        try:
            util.WaitFor(lambda: verify_message_condition(),
                         _VERIFICATION_TIME_OUT)
        except util.TimeoutException:
            raise error.TestFail('Expected error message for key string '
                                 + key_string + ' is not displayed.')

    def setup_mock(self, js_code):
        """Sets up mock for the test.

        @param js_code: The mock javascript code to be executed.
        """

        mock_tab = self.browser.tabs[_MAIN_TAB_IDX]
        mock_tab.Activate()
        mock_tab.Navigate(_MAIN_URL)
        mock_tab.ExecuteJavaScript(js_code)


    def setup_mock_for_error_from_server(self, key_string):
        """Set up mock for test with errors from ECHO server.

        For each case, it mocks specific error key_string returned from ECHO
        server.

        @param key_string: The key_string returned from ECHO server.
        """

        js_code = _MOCK_ORIGIN_SUCCESS_JS + _MOCK_CONSENT_ALLOW_JS + """
            echo.getXHR = function() {
                var xhr = {};
                xhr.open = function(action, endpoint) {};
                xhr.setRequestHeader = function(type, app) {};
                xhr.responseText =
                    '{"result": {"result": "NOT_ELIGIBLE", "message": %s}}';
                xhr.send = function(params) {
                    xhr.onload();
                };
                return xhr;
            }
        """
        js_code = js_code % key_string
        self.setup_mock(js_code)


    def test_error_from_server(self, key_string):
        """Test cases where errors returned from ECHO server.

        @param key_string: the key_string returned from ECHO server.
        """

        if key_string == 'GENERIC_ERROR_MESSAGE':
            self.setup_mock_for_error_from_server('null')
        else:
            self.setup_mock_for_error_from_server('"' + key_string + '"')
        self.send_request()
        self.verify_message(key_string)


    def test_origin_failure(self):
        """Test when the origin verification fails."""

        js_code = """
            echo.verifyOrigin = function(origin, requestNonce, successCallback,
                                         failureCallback) {
                failureCallback();
            }
        """
        self.setup_mock(js_code)
        self.send_request()
        self.verify_message('ERROR_ORIGIN_FAILURE')


    def test_consent_denied(self):
        """Test when the user deny the request to check."""

        js_code = _MOCK_ORIGIN_SUCCESS_JS + _MOCK_CONSENT_DENY_JS
        self.setup_mock(js_code)
        self.send_request()
        self.verify_message('CONSENT_DENIED')


    def test_no_regcode(self):
        """Test when no reg code can be found in the Chromebook."""

        js_code = _MOCK_ORIGIN_SUCCESS_JS + _MOCK_CONSENT_ALLOW_JS + """
            echo.getDeviceCode = function(isGroupType, callback) {
                callback();
            }
        """
        self.setup_mock(js_code)
        self.send_request()
        self.verify_message('ERROR_NO_REGCODE')


    def test_max_enrollment_count_exceeded(self):
        """Test when the offer is redeemed in the Chromebook before."""

        self.test_error_from_server('MAX_ENROLLMENT_COUNT_EXCEEDED')


    def test_device_not_eligible(self):
        """Test when the device is not eligible for the offer."""

        self.test_error_from_server('DEVICE_NOT_ELIGIBLE')


    def test_otc_service_does_not_match(self):
        """Test when the otc doesn't match service."""

        self.test_error_from_server('OTC_SERVICE_DOES_NOT_MATCH')


    def test_device_no_longer_eligible(self):
        """Test when the device is no longer eligible."""

        self.test_error_from_server('DEVICE_NO_LONGER_ELIGIBLE')


    def test_device_sku_not_eligible(self):
        """Test when the sku is not eligible."""

        self.test_error_from_server('DEVICE_SKU_NOT_ELIGIBLE')


    def test_regcode_invalid(self):
        """Test when the regcode in Chromebook is invalid."""

        self.test_error_from_server('REGISTRATION_CODE_INVALID')


    def test_generic_error(self):
        """Test for generic message."""

        self.test_error_from_server('GENERIC_ERROR_MESSAGE')


    def run_once(self):
       with chrome.Chrome() as cr:
           self.browser = cr.browser
           self.browser.tabs.New().Navigate(_MAIN_URL)
           self.browser.tabs.New().Navigate(_BROKER_URL)
           self.browser.tabs.New().Navigate(_NOT_ELIGIBLE_URL)
           self.test_origin_failure()
           self.test_consent_denied()
           self.test_no_regcode()
           self.test_max_enrollment_count_exceeded()
           self.test_device_not_eligible()
           self.test_otc_service_does_not_match()
           self.test_device_no_longer_eligible()
           self.test_device_sku_not_eligible()
           self.test_regcode_invalid()
           self.test_generic_error()
