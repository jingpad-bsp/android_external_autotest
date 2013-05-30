# Copyright (c) 2010 The Chromium OS Authors. All rights reserved.
# Use of this source code is governed by a BSD-style license that can be
# found in the LICENSE file.

import os, string, time, gtk
from autotest_lib.client.bin import utils
from autotest_lib.client.common_lib import error
from autotest_lib.client.cros import cros_ui, cros_ui_test, httpd

class desktopui_ImeTest(cros_ui_test.UITest):
    version = 1
    preserve_srcdir = True

    def setup(self):
        # TODO: We shouldn't use ibusclient, we should talk to Chrome directly
        self.job.setup_dep(['ibusclient'])

    def initialize(self, creds='$default'):
        self._test_url = 'http://127.0.0.1:8000/interaction_form.html'
        self._test_server = httpd.HTTPListener(8000, docroot=self.bindir)
        self._test_server.run()

        cros_ui_test.UITest.initialize(self, creds)


    def cleanup(self):
        self._test_server.stop()
        cros_ui_test.UITest.cleanup(self)


    def log_error(self, test_name, message):
        self.job.record('ERROR', None, test_name, message)
        self._failed.append(test_name)


    # TODO(zork) We should share this with platform_ProcessPrivleges.
    # See: crosbug.com/7453
    def check_process(self, process, user=None):
        """Check if the process is running as the specified user / root.

        Args:
            process: Process name to check.
            user: User process must run as; ignored if None.
        """

        # Get the process information
        pscmd = 'ps -o f,euser,ruser,suser,fuser,comm -C %s --no-headers'
        pscmd = pscmd % process
        ps = utils.system_output(pscmd,
                                 ignore_status=True, retain_output=True)

        pslines = ps.splitlines()

        # Fail if process is not running
        if not len(pslines):
            self.log_error('check_process %s' % process,
                           'Process %s is not running' % process)
            return

        # Check all instances of the process
        for psline in pslines:
            ps = psline.split()

            # Fail if not running as the specified user
            if user is not None:
                for uid in ps[1:5]:
                    if uid != user:
                        self.log_error('check_process %s' % process,
                                       'Process %s running as %s; expected %s' %
                                       (process, uid, user))
                        return

            # Check if process has super-user privileges
            else:
                # TODO(zork): Uncomment this once issue 2253 is resolved
                # if int(ps[0]) & 0x04:
                #    self.log_error(
                #        'check_process %s' % process,
                #        'Process %s running with super-user flag' %
                #        process)
                if 'root' in ps:
                    self.log_error('check_process %s' % process,
                                   'Process %s running as root' % process)
                    return


    # TODO: Get rid of this function.
    def run_ibusclient(self, options):
        cmd = cros_ui.xcommand_as(
            'IBUS_ADDRESS_FILE=/tmp/'
            '`ls -at /tmp/ | grep .ibus-socket | head -1`'
            '/ibus-socket-file %s %s' %
            (self.exefile, options), 'chronos')
        return utils.system_output(cmd, retain_output=True)


    # TODO: Make this function talk to chrome directly
    def preload_engines(self, engine_list):
        engine_names = string.join(engine_list, " ")
        out = self.run_ibusclient('preload_engines %s' % engine_names)
        if not 'OK' in out:
            self.log_error('preload_engines %s' % engine_names,
                           'Failed to preload engines: %s' % engine_names)


    # TODO: Make this function talk to chrome directly
    def activate_engine(self, engine_name):
        start_time = time.time()
        while time.time() - start_time < 10:
            out = self.run_ibusclient('activate_engine %s' % engine_name)
            if 'OK' in out and self.get_active_engine() == engine_name:
                return
            time.sleep(1)
        self.log_error('activate_engine',
                       'Failed to activate engine: %s' % engine_name)


    def get_active_engine(self):
        out = self.run_ibusclient('get_active_engine')
        return out.strip()


    def toggle_ime_process(self):
        ax = cros_ui.get_autox()

        # Open the config dialog.
        ax.send_hotkey('Ctrl+t')
        time.sleep(1)
        ax.send_hotkey('Ctrl+l')
        time.sleep(1)
        # Navigate to the "Languages and Input" menu.
        ax.send_text('chrome://settings/languages#lang=%s,focus=%s\n' %
                     ('en-US', 'xkb:us:altgr-intl:eng'))
        time.sleep(5)

        # Toggle the checkbox.
        ax.send_text(' ')
        time.sleep(1)

        # Close the window.
        ax.send_hotkey('Ctrl+w')
        time.sleep(1)


    def start_ime_engine(self, language, engine):
        """
        Enable an IME engine via the Chrome settings dialog.

        @param language Language ID of the IME.
        @param engine Name of the engine to enable.
        """
        ax = cros_ui.get_autox()

        # Open the config dialog.
        ax.send_hotkey('Ctrl+t')
        time.sleep(1)
        ax.send_hotkey('Ctrl+l')
        time.sleep(1)
        # Navigate to the "Languages and Input" menu.
        ax.send_text('chrome://settings/languages#focus=add,lang_add=%s\n' %
                     language)
        time.sleep(10)
        ax.send_text(' ')
        time.sleep(1)
        ax.send_hotkey('Ctrl+w')
        time.sleep(1)
        ax.send_hotkey('Ctrl+t')
        time.sleep(1)
        ax.send_hotkey('Ctrl+l')
        time.sleep(1)
        ax.send_text('chrome://settings/languages#lang=%s,focus=%s\n' %
                     (language, engine))
        time.sleep(10)

        # Toggle the checkbox.
        ax.send_text(' ')
        # The toggling can take longer than 1 sec.
        time.sleep(2)

        # Close the window.
        ax.send_hotkey('Ctrl+w')
        time.sleep(1)


    def stop_ime_engine(self, language, engine):
        """
        Remove a language from Chrome's preferred list and disable all its IMEs.

        @param language Language ID of the language to remove.
        """
        ax = cros_ui.get_autox()

        # Open the config dialog.
        ax.send_hotkey('Ctrl+t')
        time.sleep(1)
        ax.send_hotkey('Ctrl+l')
        time.sleep(1)
        ax.send_text('chrome://settings/languages#lang=%s,focus=%s\n' %
                     (language, engine))
        time.sleep(10)

        # Toggle the checkbox.
        ax.send_text(' ')
        # The toggling can take longer than 1 sec.
        time.sleep(2)
        ax.send_hotkey('Ctrl+w')
        time.sleep(1)

        # Open the config dialog.
        ax.send_hotkey('Ctrl+t')
        time.sleep(1)
        ax.send_hotkey('Ctrl+l')
        time.sleep(1)
        # Navigate to the "Languages and Input" menu.
        ax.send_text('chrome://settings/languages#lang=%s,focus=remove\n' %
                     language)
        time.sleep(10)

        # Push the button
        ax.send_text(' ')
        time.sleep(1)

        # Close the window.
        ax.send_hotkey('Ctrl+w')
        time.sleep(1)


    def get_current_text(self):
        # Because there can be a slight delay between entering text and the
        # output from the ime being received, we need to sleep here.
        time.sleep(1)
        ax = cros_ui.get_autox()

        # The DISPLAY environment variable isn't set, so we have to manually get
        # the proper display.
        display = gtk.gdk.Display(":0.0")
        clip = gtk.Clipboard(display, "PRIMARY")

        # Wait 10 seconds for text to be available in the clipboard, or return
        # an empty string.
        start_time = time.time()
        while time.time() - start_time < 10:
            # Select all the text so that it can be accessed via the clipboard.
            ax.send_hotkey('Ctrl-a')
            time.sleep(1)

            if clip.wait_is_text_available():
                return str(clip.wait_for_text())
            time.sleep(1)
        return ""


    def check_current_text(self, expected_string):
      # Compares the current text to the expected text, and retires on failure.
      # This makes the test a little more reliable if the system is
      # under stress.
      retries = 4
      while retries > 0:
        text = self.get_current_text()
        if text == expected_string:
          return text
        retries = retries - 1

      return text


    def test_ibus_start_process(self):
        # Check that enabling the IME launches ibus.
        self.toggle_ime_process()
        start_time = time.time()
        while time.time() - start_time < 10:
            if os.system('pgrep ^ibus-daemon$ >/dev/null') == 0:
                return
            time.sleep(1)
        self.log_error('test_ibus_start_process',
                       'ibus-daemon did not start via config')


    def test_ibus_stop_process(self):
        # Check that disabling the IME stops ibus.
        self.toggle_ime_process()
        start_time = time.time()
        while time.time() - start_time < 10:
            if os.system('pgrep ^ibus-daemon$ >/dev/null') != 0:
                return
            time.sleep(1)
        self.log_error('test_ibus_stop_process',
                       'ibus-daemon did not stop via config')


    def test_keyboard_shortcut(self):
        expected_initial_engine = 'xkb:us::eng'
        expected_other_engine = 'xkb:us:altgr-intl:eng'

        current_engine = self.get_active_engine()
        if current_engine != expected_initial_engine:
            self.log_error('test_keyboard_shortcut',
                           'Initial engine is %s, expected %s' %
                           (current_engine, expected_initial_engine))
        ax = cros_ui.get_autox()
        ax.send_hotkey('Ctrl-l')
        # If we don't sleep here sometimes the following keys are not received
        time.sleep(1)
        ax.send_hotkey('Ctrl-space')
        start_time = time.time()
        while time.time() - start_time < 10:
            current_engine = self.get_active_engine()
            if current_engine == expected_other_engine:
                ax.send_hotkey('Ctrl-space')
                return
            time.sleep(1)
        self.log_error('test_keyboard_shortcut',
                       'Current engine is %s, expected %s' %
                       (current_engine, expected_other_engine))


    def test_engine(self, language, engine_name, input_string, expected_string):
        self.start_ime_engine(language, engine_name)
        self.activate_engine(engine_name)
        self.test_engine_omnibox(language, engine_name, input_string,
                                 expected_string)
        # TODO: Re-enable this test when we determine how to handle the timeout
        # on localhost.
        #self.test_engine_form(language, engine_name, input_string,
        #                      expected_string)
        self.activate_engine('xkb:us::eng')
        self.stop_ime_engine(language, engine_name)


    def test_engine_omnibox(self, language, engine_name, input_string,
                            expected_string):
        ax = cros_ui.get_autox()

        # Focus on the omnibox so that we can enter text.
        ax.send_hotkey('Ctrl-l')

        # Sometimes there is a slight delay before input can be received in the
        # omnibox.
        time.sleep(1)

        ax.send_text(input_string)

        text = self.check_current_text(expected_string)
        if text != expected_string:
            self.log_error(
                'test_engine %s in omnibox' % engine_name,
                'Engine %s failed : Got %s, expected %s' % (
                    engine_name, text, expected_string))
        # Clear the omnibox for future tests.
        ax.send_hotkey('BackSpace')


    def test_engine_form(self, language, engine_name, input_string,
                         expected_string):
        ax = cros_ui.get_autox()
        # Go to the page containing the form.
        self.activate_engine('xkb:us::eng')
        ax.send_hotkey("Ctrl+l")
        time.sleep(1)
        ax.send_text("%s \n" % self._test_url)
        time.sleep(1)
        self.activate_engine(engine_name)

        ax.send_text(input_string)
        text = self.check_current_text(expected_string)
        if text != expected_string:
            self.log_error(
                'test_engine %s in form' % engine_name,
                'Engine %s failed : Got %s, expected %s' % (
                    engine_name, text, expected_string))


    def run_once(self):
        self._failed = []
        dep = 'ibusclient'
        dep_dir = os.path.join(self.autodir, 'deps', dep)
        self.job.install_pkg(dep, 'dep', dep_dir)

        self.exefile = os.path.join(self.autodir,
                                    'deps/ibusclient/ibusclient')

        # Before we try to activate the options menu, we need to wait for
        # previous actions to complete.  Most notable is that keystrokes
        # immediately after login get lost.
        time.sleep(5)

        self.test_ibus_start_process()

        self.check_process('ibus-daemon', user='chronos')
        self.check_process('ibus-memconf', user='chronos')

        self.test_keyboard_shortcut()
        self.test_engine('ja', 'mozc', 'nihongo \n',
                         '\xE6\x97\xA5\xE6\x9C\xAC\xE8\xAA\x9E')
        self.test_engine('zh-TW', 'mozc-chewing', 'hol \n', '\xE6\x93\x8D')
        self.test_engine('ko', 'mozc-hangul', 'wl ', '\xEC\xA7\x80 ')
        self.test_engine('zh-CN', 'pinyin', 'nihao ',
                         '\xE4\xBD\xA0\xE5\xA5\xBD')
        self.test_engine('zh-TW', 'm17n:zh:quick', 'aa ', '\xE9\x96\x93')

        self.test_ibus_stop_process()

        if len(self._failed) != 0:
            raise error.TestFail(
                'Failed: %s' % ','.join(self._failed))
