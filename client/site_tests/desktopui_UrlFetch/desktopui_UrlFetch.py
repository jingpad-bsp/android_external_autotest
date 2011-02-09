# Copyright (c) 2010 The Chromium OS Authors. All rights reserved.
# Use of this source code is governed by a BSD-style license that can be
# found in the LICENSE file.

import logging, os, time, utils
from autotest_lib.client.bin import test
from autotest_lib.client.common_lib import error
from autotest_lib.client.cros import constants, cros_ui, login

class desktopui_UrlFetch(test.test):
    version = 1

    def run_once(self):
        url = 'http://www.youtube.com'
        cookie_expected = 'VISITOR_INFO1_LIVE'

        os.chdir(self.bindir)

        # Select correct binary.
        cpuType = utils.get_cpu_arch()
        url_fetch_test = 'url_fetch_test'
        if cpuType == "arm":
            url_fetch_test += '.arm'

        # Stop chrome from restarting and kill login manager.
        try:
            orig_pid = utils.system_output('pgrep %s' %
                constants.SESSION_MANAGER)
            open(constants.DISABLE_BROWSER_RESTART_MAGIC_FILE, 'w').close()
        except IOError, e:
            logging.debug(e)
            raise error.TestError('Failed to disable browser restarting.')

        # We kill with signal 9 so that the session manager doesn't exit.
        # If the session manager sees Chrome exit normally, it exits.
        login.nuke_process_by_name(name=constants.BROWSER, with_prejudice=True)

        clean_exit = False
        try:
            new_pid = utils.system_output('pgrep %s' %
                constants.SESSION_MANAGER)
            if orig_pid != new_pid:
                raise error.TestFail(
                    'session_manager restarted when chrome was killed')

            # Copy over chrome, chrome.pak, locales, chromeos needed for test.
            utils.system('cp -r %s/* .' % '/opt/google/chrome')

            cros_ui.xsystem('./%s --url=%s --wait_cookie_name=%s'
                                % (url_fetch_test, url, cookie_expected))
            clean_exit = True

        except error.CmdError, e:
            logging.debug(e)
            raise error.TestFail('Url Fetch test was unsuccessful for %s %s %s'
                                 % (url, cookie_expected, os.getcwd()))
        finally:
            # Allow chrome to be restarted again.
            os.unlink(constants.DISABLE_BROWSER_RESTART_MAGIC_FILE)

            # Reset the UI but only if we need to (avoid double reset).
            if not clean_exit:
                login.nuke_login_manager()
                login.refresh_login_screen()
