# Copyright (c) 2010 The Chromium OS Authors. All rights reserved.
# Use of this source code is governed by a BSD-style license that can be
# found in the LICENSE file.

import os, string, time, gtk
from autotest_lib.client.bin import site_ui_test, test
from autotest_lib.client.common_lib import error, site_ui, utils


class desktopui_ImeTest(site_ui_test.UITest):
    version = 1
    preserve_srcdir = True

    def setup(self):
        # TODO: We shouldn't use ibusclient, we should talk to Chrome directly
        self.job.setup_dep(['ibusclient'])


    # TODO: Get rid of this function.
    def run_ibusclient(self, options):
        cmd = site_ui.xcommand_as('%s %s' % (self.exefile, options), 'chronos')
        return utils.system_output(cmd, retain_output=True)


    # TODO: Make this function talk to chrome directly
    def preload_engines(self, engine_list):
        engine_names = string.join(engine_list, " ")
        out = self.run_ibusclient('preload_engines %s' % engine_names)
        if not 'OK' in out:
            raise error.TestFail('Failed to preload engines: %s' % engine_names)


    # TODO: Make this function talk to chrome directly
    def activate_engine(self, engine_name):
        start_time = time.time()
        while time.time() - start_time < 10:
            out = self.run_ibusclient('activate_engine %s' % engine_name)
            if 'OK' in out and self.get_active_engine() == engine_name:
                return
            time.sleep(1)
        raise error.TestFail('Failed to activate engine: %s' % engine_name)


    def get_active_engine(self):
        out = self.run_ibusclient('get_active_engine')
        return out.strip()


    # TODO: Make this function set the config value directly, instead of
    # attempting to navigate the UI.
    def toggle_ime_process(self):
        ax = self.get_autox()

        # Open the config dialog.
        ax.send_hotkey('Ctrl+t')
        time.sleep(1)
        ax.send_hotkey('Ctrl+l')
        time.sleep(1)
        # Navigate to the "Languages and Input" menu.
        ax.send_text('chrome://settings/language\n')
        time.sleep(5)

        # Select the "International keyboard" checkbox.
        ax.send_text('\t\t\t\t\t\t\t\t\t\t\t\t\t\t ')

        # Close the window.
        ax.send_hotkey('Ctrl+w')
        time.sleep(1)


    def get_current_text(self):
        # Because there can be a slight delay between entering text and the
        # output from the ime being received, we need to sleep here.
        time.sleep(1)
        ax = self.get_autox()

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

            if clip.wait_is_text_available():
                return str(clip.wait_for_text())
            time.sleep(1)
        return ""


    def test_ibus_start_process(self):
        # Check that enabling the IME launches ibus.
        self.toggle_ime_process()
        start_time = time.time()
        while time.time() - start_time < 10:
            if os.system('pgrep ^ibus-daemon$') == 0:
                return
            time.sleep(1)
        raise error.TestFail('ibus-daemon did not start via config')


    def test_ibus_stop_process(self):
        # Check that disabling the IME stops ibus.
        self.toggle_ime_process()
        start_time = time.time()
        while time.time() - start_time < 10:
            if os.system('pgrep ^ibus-daemon$') != 0:
                return
            time.sleep(1)
        raise error.TestFail('ibus-daemon did not stop via config')


    def test_keyboard_shortcut(self):
        expected_initial_engine = 'xkb:us::eng'
        expected_other_engine = 'xkb:us:altgr-intl:eng'

        current_engine = self.get_active_engine()
        if current_engine != expected_initial_engine:
            raise error.TestFail('Initial engine is %s, expected %s' %
                                 (current_engine,
                                  expected_initial_engine))
        ax = self.get_autox()
        ax.send_hotkey('Ctrl-l')
        ax.send_hotkey('Ctrl-space')
        start_time = time.time()
        while time.time() - start_time < 10:
            current_engine = self.get_active_engine()
            if current_engine == expected_other_engine:
                ax.send_hotkey('Ctrl-space')
                return
            time.sleep(1)
        raise error.TestFail('Current engine is %s, expected %s' %
                             (current_engine,
                              expected_other_engine))


    def test_engine(self, engine_name, input_string, expected_string):
        self.preload_engines([engine_name])
        self.activate_engine(engine_name)

        ax = self.get_autox()

        # Focus on the omnibox so that we can enter text.
        ax.send_hotkey('Ctrl-l')

        # Sometimes there is a slight delay before input can be received in the
        # omnibox.
        time.sleep(1)

        ax.send_text(input_string)

        text = self.get_current_text()
        if text != expected_string:
            raise error.TestFail(
                'Engine %s failed: Got %s, expected %s' % (engine_name, text,
                                                           expected_string))


    def run_once(self):
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
        self.test_keyboard_shortcut()
        self.test_engine('mozc', 'nihongo \n',
                         '\xE6\x97\xA5\xE6\x9C\xAC\xE8\xAA\x9E')
        self.test_engine('chewing', 'hol \n', '\xE6\x93\x8D')
        self.test_engine('hangul', 'wl ', '\xEC\xA7\x80 ')
        self.test_engine('pinyin', 'nihao ', '\xE4\xBD\xA0\xE5\xA5\xBD')

        # Run a test on English last, so that we can type in English to
        # turn off the IME.
        self.test_engine('xkb:us::eng', 'asdf', 'asdf')
        self.test_ibus_stop_process()
