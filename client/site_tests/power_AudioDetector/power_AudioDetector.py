# Copyright (c) 2012 The Chromium OS Authors. All rights reserved.
# Use of this source code is governed by a BSD-style license that can be
# found in the LICENSE file.

import logging, os, threading, time
from autotest_lib.client.bin import test, utils
from autotest_lib.client.common_lib import error
from autotest_lib.client.cros import cros_ui_test, rtc
from autotest_lib.client.cros.audio import audio_helper

def restart_process(name):
    if utils.system_output('status %s' % name).find('start/running') != -1:
        utils.system_output('restart %s' % name)
    else:
        utils.system_output('start %s' % name)


class power_AudioDetector(cros_ui_test.UITest):
    version = 1
    _pref_path = '/var/lib/power_manager'
    _backup_path = '/tmp/var_lib_power_manager_backup'
    _audio_loop_time_sec = 10

    def run_once(self, run_time_sec=60):
        # Start powerd if not started.  Set timeouts for quick idle events.
        # Save old prefs in a backup directory.
        # TODO(crosbug.com/36382): make this a library function.
        pref_path = self._pref_path
        os.system('mkdir %s' % self._backup_path)
        os.system('mv %s/* %s' % (pref_path, self._backup_path))
        prefs = { 'disable_idle_suspend' : 0,
                  'react_ms'             : 10000,
                  'plugged_dim_ms'       : 10000,
                  'plugged_off_ms'       : 20000,
                  'plugged_suspend_ms'   : 30000,
                  'unplugged_dim_ms'     : 10000,
                  'unplugged_off_ms'     : 20000,
                  'unplugged_suspend_ms' : 30000 }
        for name in prefs:
            os.system('echo %d > %s/%s' % (prefs[name], pref_path, name))

        restart_process('powerd')

        self.login()

        # Set a low audio volume to avoid annoying people during tests.
        audio_helper.AudioHelper(None).set_volume_levels(10, 100)

        # Start playing audio file.
        self._enable_audio_playback = True
        thread = threading.Thread(target=self._play_audio)
        thread.start()

        # Set an alarm to wake up the system in case the audio detector fails
        # and the system suspends.
        alarm_time = rtc.get_seconds() + run_time_sec
        rtc.set_wake_alarm(alarm_time)

        time.sleep(run_time_sec)

        # Stop powerd to avoid suspending when the audio stops.
        utils.system_output('stop powerd')

        # Stop audio and wait for the audio thread to terminate.
        self._enable_audio_playback = False
        thread.join(timeout=(self._audio_loop_time_sec * 2))
        if thread.is_alive():
            logging.error('Audio thread did not terminate at end of test.')

        # Check powerd log to make sure suspend was delayed due to audio, and
        # that no suspend took place.
        powerd_log_path = '/var/log/power_manager/powerd.LATEST'
        log = open(powerd_log_path, 'r').read()

        if log.find('All suspend delays accounted for. Suspending.') != -1:
            raise error.TestFail('System suspended while audio was playing.')

        if log.find('Delaying suspend because audio is playing.') == -1:
            raise error.TestFail('Could not find logging of audio delaying ' +
                                 'suspend.')


    def cleanup(self):
        if self.logged_in():
            self.logout()

        # Restore prefs, delete backup directory, and restart powerd.
        # TODO(crosbug.com/36382): make this a library function.
        pref_path = self._pref_path
        utils.system_output('rm %s/*' % pref_path)
        utils.system_output('mv %s/* %s' % (self._backup_path, pref_path))
        utils.system_output('rmdir %s' % self._backup_path)
        restart_process('powerd')


    def _play_audio(self):
        """
        Repeatedly plays audio until self._audio_playback_enabled == False.
        """
        # TODO(crosbug.com/33988): Allow for pauses in audio playback to
        # simulate delays in loading the next song.
        audio = audio_helper.AudioHelper(None)
        while self._enable_audio_playback:
            audio.play_sound(duration_seconds=self._audio_loop_time_sec)
        logging.info('Done playing audio.')
