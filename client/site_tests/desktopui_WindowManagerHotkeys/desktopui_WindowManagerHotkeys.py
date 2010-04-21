# Copyright (c) 2010 The Chromium OS Authors. All rights reserved.
# Use of this source code is governed by a BSD-style license that can be
# found in the LICENSE file.

import os, random, re, shutil, time
from autotest_lib.client.bin import site_ui_test, site_utils, test, utils
from autotest_lib.client.common_lib import error

class desktopui_WindowManagerHotkeys(site_ui_test.UITest):
    version = 1

    def __get_channel_volume(self, output, channel_name):
        """Find a channel's volume within the amixer command's output.

        Helper method used by __get_mixer_volume().

        Args:
            output: str output from "amixer get Master"
            channel_name: str name of channel, e.g. "Front Left"

        Returns:
            Channel volume as an int (0 is returned for muted channels).
        """
        regexp = '%s: Playback \d+ \[(\d+)%%\] \[(on|off)\]' % channel_name
        match = re.search(regexp, output)
        if not match:
            raise error.TestError(
                'Unable to get volume for channel "%s"' % channel_name)
        if match.group(2) == 'off':
            return 0
        return int(match.group(1))

    def __get_mixer_volume(self):
        """Get the current mixer volume.

        Returns:
            A two-element tuple consisting of the int volume of the left and
                right channels.
        """
        output = utils.system_output('/usr/bin/amixer get Master')
        return (self.__get_channel_volume(output, 'Front Left'),
                self.__get_channel_volume(output, 'Front Right'))

    def run_once(self):
        ax = self.get_autox()

        # Start a terminal and wait for it to get the focus.
        # TODO: This is a bit of a hack.  To watch for the terminal getting
        # the focus, we create a new window, wait for it to get the focus,
        # and then launch the terminal and wait for our window to lose the
        # focus (AutoX isn't notified about focus events on the terminal
        # window itself).  It's maybe cleaner to add a method to AutoX to
        # get the currently-focused window and then just poll that after
        # starting the terminal until it changes.
        win = ax.create_and_map_window()
        info = ax.get_window_info(win.id)
        ax.await_condition(
            lambda: info.is_focused,
            desc='Waiting for window to get focus')
        ax.send_hotkey('Ctrl-Alt-t')
        ax.await_condition(
            lambda: not info.is_focused,
            desc='Waiting for window to lose focus')

        # Type in it to create a file in /tmp and exit.
        temp_filename = '/tmp/desktopup_WindowManagerHotkeys_%d' % time.time()
        ax.send_text('touch %s\n' % temp_filename)
        ax.send_text('exit\n')
        site_utils.poll_for_condition(
            lambda: os.access(temp_filename, os.F_OK),
            error.TestFail(
                'Waiting for %s to be created from terminal' % temp_filename))
        os.remove(temp_filename)

        # Press the Print Screen key and check that a screenshot is written.
        screenshot_dir = '/home/chronos/user/Downloads/Screenshots'
        shutil.rmtree(screenshot_dir, ignore_errors=True)
        ax.send_hotkey('Print')
        site_utils.poll_for_condition(
            lambda: os.access(screenshot_dir, os.F_OK) and \
                    os.listdir(screenshot_dir),
            error.TestFail(
                'Waiting for screenshot in %s' % screenshot_dir))
        shutil.rmtree(screenshot_dir, ignore_errors=True)

        # Make sure that the mixer is unmuted and at 50% before we test the
        # audio key bindings.
        utils.system('/usr/bin/amixer sset Master unmute 50%')

        ax.send_hotkey('XF86AudioRaiseVolume')
        site_utils.poll_for_condition(
            lambda: self.__get_mixer_volume() == (55, 55),
            error.TestFail('Waiting for volume to be increased'))

        ax.send_hotkey('XF86AudioLowerVolume')
        site_utils.poll_for_condition(
            lambda: self.__get_mixer_volume() == (50, 50),
            error.TestFail('Waiting for volume to be decreased'))

        ax.send_hotkey('XF86AudioMute')
        site_utils.poll_for_condition(
            lambda: self.__get_mixer_volume() == (0, 0),
            error.TestFail('Waiting for volume to be muted'))

        ax.send_hotkey('XF86AudioRaiseVolume')
        site_utils.poll_for_condition(
            lambda: self.__get_mixer_volume() == (55, 55),
            error.TestFail('Waiting for volume to be increased'))
