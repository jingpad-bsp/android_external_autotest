# Copyright 2016 The Chromium OS Authors. All rights reserved.
# Use of this source code is governed by a BSD-style license that can be
# found in the LICENSE file.
#
# arc_util.py is supposed to be called from chrome.py for ARC specific logic.
# It should not import arc.py since it will create a import loop.

import logging
import os
import shutil
import tempfile

from autotest_lib.client.bin import utils
from autotest_lib.client.common_lib import error
from autotest_lib.client.common_lib import file_utils
from autotest_lib.client.common_lib.cros import arc_common
from autotest_lib.client.cros import cryptohome
from telemetry.internal.browser import extension_page

_VAR_LOGCAT_DIR = '/var/log/arc-logd'
_ARC_SUPPORT_HOST_URL = 'chrome-extension://cnbgggchhmkkdmeppjobngjoejnihlei/'
_USERNAME = 'powerloadtest@gmail.com'
_USERNAME_DISPLAY = 'power.loadtest@gmail.com'
_PLTP_URL = 'https://sites.google.com/a/chromium.org/dev/chromium-os' \
                '/testing/power-testing/pltp/pltp'


def should_start_arc(arc_mode):
    """
    Determines whether ARC should be started.

    @param arc_mode: mode as defined in arc_common.

    @returns: True or False.

    """
    logging.debug('ARC is enabled in mode ' + str(arc_mode))
    assert arc_mode is None or arc_mode in arc_common.ARC_MODES
    return arc_mode in [arc_common.ARC_MODE_ENABLED,
                        arc_common.ARC_MODE_ENABLED_ASYNC]


def get_extra_chrome_flags():
    """Returns extra Chrome flags for ARC tests to run"""
    return ['--disable-arc-opt-in-verification']


def post_processing_after_browser(chrome):
    """
    Called when a new browser instance has been initialized.

    Note that this hook function is called regardless of arc_mode.

    @param chrome: Chrome object.

    """
    # Wait for Android container ready if ARC is enabled.
    if chrome.arc_mode == arc_common.ARC_MODE_ENABLED:
        arc_common.wait_for_android_boot()


def pre_processing_before_close(chrome):
    """
    Called when the browser instance is being closed.

    Note that this hook function is called regardless of arc_mode.

    @param chrome: Chrome object.

    """
    if not should_start_arc(chrome.arc_mode):
        return

    # Save the logcat data just before the log-out.
    # TODO(b/29138685): stop android before saving logcat, in order to
    # avoid a race of log rotation happening during trying to save.
    try:
        _backup_arc_logcat(chrome.username)
    except Exception:
        # Log cat backup is also nice-to-have stuff. Do not make it as a
        # fatal error.
        logging.exception('Failed to back up the logcat data.')


def _backup_arc_logcat(username):
    """
    Copies ARC's logcat files to /var/log/arc-logd.

    @param username: Login user name.

    """
    arc_logcat_dir = os.path.join(
            cryptohome.system_path(username),
            'android-data', 'data', 'misc', 'logd')

    if not os.path.isdir(arc_logcat_dir):
        logging.error('Missing logcat directory.')
        return

    # Just in case there are old data.
    shutil.rmtree(_VAR_LOGCAT_DIR, ignore_errors=True)

    os.makedirs(_VAR_LOGCAT_DIR)
    for filename in os.listdir(arc_logcat_dir):
        if not filename.startswith('logcat'):
            # Do not copy other than logcat files.
            continue
        shutil.copy2(os.path.join(arc_logcat_dir, filename),
                     os.path.join(_VAR_LOGCAT_DIR, filename))


def set_browser_options_for_opt_in(b_options):
    """
    Setup Chrome for gaia login and opt_in.

    @param b_options: browser options object used by chrome.Chrome.

    """
    b_options.username = _USERNAME
    with tempfile.NamedTemporaryFile() as pltp:
        file_utils.download_file(_PLTP_URL, pltp.name)
        b_options.password = pltp.read().rstrip()
    b_options.disable_default_apps = False
    b_options.disable_component_extensions_with_background_pages = False
    b_options.gaia_login = True


def opt_in(browser):
    """
    Step through opt in and wait for it to complete.

    @param browser: chrome.Chrome broswer object.

    @raises: error.TestFail if opt in fails.

    """
    logging.info('Initializing arc opt-in flow.')

    opt_in_extension_id = extension_page.UrlToExtensionId(_ARC_SUPPORT_HOST_URL)
    try:
        extension_main_page = browser.extensions.GetByExtensionId(
            opt_in_extension_id)[0]
    except Exception, e:
        raise error.TestFail('Could not locate extension for arc opt-in.' +
                             'Make sure disable_default_apps is False.')

    settings_tab = browser.tabs[0]
    settings_tab.Navigate('chrome://settings')
    settings_tab.WaitForDocumentReadyStateToBeComplete()

    try:
        js_code_assert_arc_option_available = """
            assert(document.getElementById('android-apps-enabled'));
        """
        settings_tab.ExecuteJavaScript(js_code_assert_arc_option_available)
    except Exception, e:
        raise error.TestFail('Could not locate section in chrome://settings' +
                             ' to enable arc. Make sure arc is available.')

    # Skip enabling for managed users, since value is policy enforced.
    # Return early if a managed user has ArcEnabled set to false.
    js_code_is_managed = ('document.getElementById('
                          '"android-apps-enabled").disabled')
    is_managed = settings_tab.EvaluateJavaScript(js_code_is_managed)
    if is_managed:
        logging.info('Determined that ARC++ is managed by user policy.')
        js_code_policy_value = ('document.getElementById('
                                '"android-apps-enabled").checked')
        policy_value = settings_tab.EvaluateJavaScript(js_code_policy_value)
        if not policy_value:
            logging.info('Returning early since ARC++ is policy enforced off.')
            return
    else:
        js_code_enable_arc = ('Preferences.setBooleanPref(\'arc.enabled\', '
                                                          'true, true)')
        settings_tab.ExecuteJavaScript(js_code_enable_arc)

    js_code_did_start_conditions = ['appWindow', 'termsView',
            ('!appWindow.contentWindow.document'
             '.getElementById(\'start\').hidden')]

    extension_main_page.WaitForDocumentReadyStateToBeComplete()
    for condition in js_code_did_start_conditions:
        extension_main_page.WaitForJavaScriptExpression(condition, 60.0)

    js_code_click_agree = """
        doc = appWindow.contentWindow.document;
        agree_button_element = doc.getElementById('button-agree');
        agree_button_element.click();
    """
    extension_main_page.ExecuteJavaScript(js_code_click_agree)

    js_code_is_lso_section_active = """
        !appWindow.contentWindow.document.getElementById('lso').hidden
    """
    try:
        extension_main_page.WaitForJavaScriptExpression(
            js_code_is_lso_section_active, 120)
    except Exception, e:
        raise error.TestFail('Error occured while waiting for lso session. This' +
                             'may have been caused if gaia login was not used.')

    web_views = utils.poll_for_condition(
            extension_main_page.GetWebviewContexts, timeout=60,
            exception=error.TestError('WebviewContexts error during opt in!'))

    js_code_is_sign_in_button_enabled = """
        !document.getElementById('submit_approve_access')
            .hasAttribute('disabled')
    """
    web_views[0].WaitForJavaScriptExpression(
            js_code_is_sign_in_button_enabled, 60.0)

    js_code_click_sign_in = """
        sign_in_button_element = document.getElementById('submit_approve_access');
        sign_in_button_element.click();
    """
    web_views[0].ExecuteJavaScript(js_code_click_sign_in)

    # Wait for app to close (i.e. complete sign in).
    SIGN_IN_TIMEOUT = 120
    try:
        extension_main_page.WaitForJavaScriptExpression('!appWindow',
                                                        SIGN_IN_TIMEOUT)
    except Exception, e:
        js_read_error_message = """
            err = appWindow.contentWindow.document.getElementById(
                    "error-message");
            if (err) {
                err.innerText;
            }
        """
        err_msg = extension_main_page.EvaluateJavaScript(js_read_error_message)
        err_msg = err_msg.strip()
        logging.error('Error: %s', err_msg.strip())
        if err_msg:
            raise error.TestFail('Opt-in app error: %s' % err_msg)
        else:
            raise error.TestFail('Opt-in app did not finish running after %s '
                                 'seconds!' % SIGN_IN_TIMEOUT)

    logging.info('Arc opt-in flow complete.')
