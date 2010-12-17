# Copyright (c) 2010 The Chromium OS Authors. All rights reserved.
# Use of this source code is governed by a BSD-style license that can be
# found in the LICENSE file.

import os, string, time, gtk
from autotest_lib.client.bin import test
from autotest_lib.client.common_lib import error, utils
from autotest_lib.client.cros import ui

class desktopui_ImeLogin(test.test):
    version = 1

    def setup(self):
        # Rank in the "others language" selection menu
        self._japanese_rank = 22
        # (X, Y) position from the top right edge (hopefully invariant)
        self._language_selector_pos = (75, 15)


    def log_error(self, test_name, message):
        self.job.record('ERROR', None, test_name, message)
        self._failed.append(test_name)


    # TODO(timothe): Share this with desktopui_ImeTest.
    def get_current_text(self):
        # Because there can be a slight delay between entering text and the
        # output from the ime being received, we need to sleep here.
        time.sleep(1)
        ax = ui.get_autox()

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


    def get_current_keyboard_layout(self):
        # Typical output of the "setxkbmap -print" command:
        # xkb_keymap {
        # xkb_keycodes  { include "evdev+aliases(qwerty)"};
        # xkb_types     { include "complete"};
        # xkb_compat    { include "complete+japan"};
        # xkb_symbols   { include "pc+jp+inet(evdev)+group(alts_toggle)"};
        # xkb_geometry  { include "pc(pc105)"};
        # };
        # This will return the "jp" on the 5th line.
        cmd = "setxkbmap -print | grep xkb_symbols | awk '{print $4}' | awk\
               -F\"+\" '{print $2}'"
        cmd_result = utils.system_output(cmd, ignore_status=True,
                                         retain_output=True)
        return cmd_result


    def change_ui_language(self, language):
        # TODO(timothe): Create a lookup table to track the position of each
        # language in the list.
        # That position changes relative to the selected language
        # so it is difficult.
        ax = ui.get_autox()
        # Navigate to the language selection and select Japanese.
        navigate_to_ui_lang = ["Tab", "Tab", "Tab", "space", "Up", "Right"]
        go_to_japanese = ["Down"] * self._japanese_rank
        for key_action in navigate_to_ui_lang + go_to_japanese + ['space']:
            ax.send_hotkey(key_action)


    def test_login_screen(self, language, input_text, expected_text):
        # Setting desired UI language.
        self.change_ui_language(language)

        # Change the keyboard layout to the one we want.
        ax = ui.get_autox()
        ax.send_hotkey("Ctrl+space")
        time.sleep(1)

        current_layout = self.get_current_keyboard_layout()
        if current_layout != language:
            # If it is not working the first time we try, that means the
            # ibus client was not run once before, so we change to a manual
            # activation via the mouse.
            width, height = ax.get_screen_size()
            ax.move_pointer(width - self._language_selector_pos[0],
                            self._language_selector_pos[1])
            ax.press_button(1)
            ax.release_button(1)
            ax.send_hotkey("Down")
            ax.send_hotkey("Return")

            # Wait for 10 seconds max.
            start_time = time.time()
            could_not_change_layout = True
            while(time.time() - start_time < 10):
              current_layout = self.get_current_keyboard_layout()
              if current_layout == language:
                could_not_change_layout = False
                break
              time.sleep(1)
            if could_not_change_layout:
              self.log_error(
                'test_login_screen',
                'Could not change the layout to japanese, got : %s' %
                current_layout)

        # Enter text in the login box and test.
        ax.send_text(input_text)
        text = self.get_current_text()
        if text != expected_text:
            self.log_error(
                'test_login_screen',
                'Test in japanese failed : Got %s, expected %s' % (
                    text, expected_text))
        ax.send_hotkey("BackSpace")

        # Brings back the english interface.
        ax.send_hotkey("Tab")
        ax.send_hotkey("Tab")
        ax.send_hotkey("Tab")
        ax.send_hotkey("space")
        ax.send_hotkey("Down")
        ax.send_hotkey("space")
        ax.send_hotkey("Tab")


    def run_once(self):
        self._failed = []

        self.test_login_screen("jp", "loguin@google.co.jp",
                               "loguin\"google.co.jp")

        if len(self._failed) != 0:
            raise error.TestFail('Failed: %s' % ','.join(self._failed))
