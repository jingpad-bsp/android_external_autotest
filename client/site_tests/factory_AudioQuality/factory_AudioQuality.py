# -*- coding: utf-8 -*-
# Copyright (c) 2012 The Chromium OS Authors. All rights reserved.
# Use of this source code is governed by a BSD-style license that can be
# found in the LICENSE file.


# DESCRIPTION :
#
# This is a factory test for audio quality. External equipment will send
# command through ethernet to configure the audio loop path. Note that it's
# External equipment's responsibility to capture and analyze the audio signal.

import os
import re
import select
import socket
import subprocess
import tempfile
import threading
import time

from autotest_lib.client.bin import test
from autotest_lib.client.common_lib import error, utils
from autotest_lib.client.cros import factory_setup_modules
from autotest_lib.client.cros.audio import audio_helper
from cros.factory.test import factory
from cros.factory.test.test_ui import UI
from cros.factory.test.event import Event
from cros.factory.test import ui as ful
from cros.factory.utils import net_utils


# Host test machine crossover connected to DUT, fix local ip and port for
# communication in between.
_HOST = ''
_PORT = 8888
_LOCAL_IP = '192.168.1.2'

# Label strings.
_LABEL_CONNECTED = 'Connected\n已连线\n'
_LABEL_WAITING = 'Waiting for command\n等待指令中\n'
_LABEL_AUDIOLOOP = 'Audio looping\n音源回放中\n'
_LABEL_SPEAKER_MUTE_OFF = 'Speaker on\n喇叭开启\n'
_LABEL_DMIC_ON = 'Dmic on\nLCD mic开启\n'
_LABEL_PLAYTONE_LEFT = ('Playing tone to left channel\n'
                        '播音至左声道\n')
_LABEL_PLAYTONE_RIGHT = ('Playing tone to right channel\n'
                         '播音至右声道\n')

# Regular expression to match external commands.
_LOOP_0_RE = re.compile("(?i)loop_0")
_LOOP_1_RE = re.compile("(?i)loop_1")
_LOOP_2_RE = re.compile("(?i)loop_2")
_LOOP_3_RE = re.compile("(?i)loop_3")
_XTALK_L_RE = re.compile("(?i)xtalk_l")
_XTALK_R_RE = re.compile("(?i)xtalk_r")
_MULTITONE_RE = re.compile("(?i)multitone")
_SEND_FILE_RE = re.compile("(?i)send_file\,\s*[^\,]+\,\s*(\d)+$")
_SWEEP_RE = re.compile("(?i)sweep")
_TEST_COMPLETE_RE = re.compile("(?i)test_complete")
_RESULT_PASS_RE = re.compile("(?i)result_pass")
_RESULT_FAIL_RE = re.compile("(?i)result_fail")

# Common mixer settings for special audio configurations, board specific
# settings should goes to each test list.
_DMIC_SWITCH_MIXER_SETTINGS = []
_INIT_MIXER_SETTINGS = [{'name': '"HP/Speaker Playback Switch"',
                         'value': 'on'},
                        {'name': '"Master Playback Volume"',
                         'value': '90,90'}]
_UNMUTE_SPEAKER_MIXER_SETTINGS = [{'name': '"HP/Speaker Playback Switch"',
                                   'value': 'off'}]
_MUTE_LEFT_MIXER_SETTINGS = [{'name': '"Master Playback Switch"',
                              'value': 'off,on'}]
_MUTE_RIGHT_MIXER_SETTINGS = [{'name': '"Master Playback Switch"',
                               'value': 'on,off'}]

# Logs
_LABEL_FAIL_LOGS = 'Test fail, find more detail in log.'

class factory_AudioQuality(test.test):
    version = 2
    preserve_srcdir = True

    def handle_connection(self, conn, *args):
        '''
        Asynchronous handler for socket connection.
        '''
        line = conn.recv(1024)
        if line:
            factory.console.info("Received command %s" % line)
        else:
            return False

        for key in self._handlers.iterkeys():
            if key.match(line):
                self._handlers[key](conn, line)
                break

        # Respond by the received command with '_OK' postfix.
        conn.send(line + '_OK')
        factory.console.info('Respond OK')

        if self._test_complete:
            factory.console.info('Test completed')
            time.sleep(3)
            if self._test_passed:
                self.ui.Pass()
            else:
                self.ui.Fail(_LABEL_FAIL_LOGS)
        return False

    def start_loop(self):
        '''
        Starts the internal audio loopback.
        '''
        if self._use_sox_loop:
            cmdargs = [self._ah.sox_path, '-t', 'alsa', self._input_dev, '-t',
                    'alsa', self._output_dev]
            self._loop_process = subprocess.Popen(cmdargs)
        else:
            cmdargs = [self._ah.audioloop_path, '-i', self._input_dev, '-o',
                    self._output_dev, '-c', str(self._loop_buffer_count)]
            self._loop_process = subprocess.Popen(cmdargs)

    def restore_configuration(self):
        '''
        Stops all the running process and restore the mute settings.
        '''
        if self._multitone_job:
            utils.nuke_subprocess(self._multitone_job.sp)
            utils.join_bg_jobs([self._multitone_job], timeout=1)
            self._multitone_job = None

        if self._sweep_job:
            utils.nuke_subprocess(self._sweep_job.sp)
            utils.join_bg_jobs([self._sweep_job], timeout=1)
            self._sweep_job = None

        if self._tone_job:
            utils.nuke_subprocess(self._tone_job.sp)
            utils.join_bg_jobs([self._tone_job], timeout=1)
            self._tone_job = None

        if self._loop_process:
            self._loop_process.kill()
            self._loop_process = None
            factory.log("Stopped audio loop process")
        self._ah.set_mixer_controls(self._init_mixer_settings)

    def handle_send_file(self, *args):
        conn = args[0]
        conn.send('OK')

        params = args[1].split(',')
        file_name = params[1]
        size = int(params[2])

        with tempfile.NamedTemporaryFile(mode='w+t') as tmp_file:
            factory.console.info("created tmp_file: %s\n" % tmp_file.name)
            tmp_file.write('File name: %s\n' % file_name)

            # A message DONE will be concatenated to the end of detailed log.
            left = size + 4
            while left > 0:
                data = conn.recv(1024)
                left -= len(data)
                tmp_file.write(data)
            tmp_file.seek(0)
            for line in tmp_file:
                self._detail_log += line

        factory.console.info("Received file %s with size %d" % (
                file_name, size))

    def handle_result_pass(self, *args):
        self._test_passed = True

    def handle_result_fail(self, *args):
        self._test_passed = False

    def handle_test_complete(self, *args):
        '''Handles test completion.

        Dumps log and runs post test script before ends this test

        '''
        factory.console.info(self._detail_log)

        self.on_test_complete()
        self._test_complete = True
        factory.console.info('%s run_once finished' % self.__class__)

    def handle_loop_none(self, *args):
        self.restore_configuration()
        self.ui.CallJSFunction('setMessage', _LABEL_WAITING)

    def handle_loop(self, *args):
        self.restore_configuration()
        self.ui.CallJSFunction('setMessage', _LABEL_AUDIOLOOP)
        self.start_loop()

    def handle_multitone(self, *args):
        '''Plays the multi-tone wav file'''
        self.restore_configuration()
        wav_path = os.path.join(self.srcdir, '10SEC.wav')
        cmdargs = ['aplay', wav_path]
        self._multitone_job = utils.BgJob(' '.join(cmdargs))

    def handle_sweep(self, *args):
        '''Plays the sweep wav file'''
        self.restore_configuration()
        wav_path = os.path.join(self.srcdir, 'sweep.wav')
        cmdargs = ['aplay', wav_path]
        self._sweep_job = utils.BgJob(' '.join(cmdargs))

    def handle_loop_jack(self, *args):
        if self._use_multitone:
            self.handle_multitone()
        else:
            self.handle_loop()
        self.ui.CallJSFunction('setMessage', _LABEL_AUDIOLOOP)

    def handle_loop_from_dmic(self, *args):
        self.handle_loop()
        self.ui.CallJSFunction('setMessage', _LABEL_AUDIOLOOP +
                _LABEL_DMIC_ON)
        self._ah.set_mixer_controls(self._dmic_switch_mixer_settings)

    def handle_loop_speaker_unmute(self, *args):
        if self._use_multitone:
            self.handle_multitone()
        else:
            self.handle_loop()
        self.ui.CallJSFunction('setMessage', _LABEL_AUDIOLOOP +
                _LABEL_SPEAKER_MUTE_OFF)
        self.unmute_speaker()

    def handle_xtalk_left(self, *args):
        self.restore_configuration()
        self.ui.CallJSFunction('setMessage', _LABEL_PLAYTONE_LEFT)
        self._ah.set_mixer_controls(self._mute_left_mixer_settings)
        self._ah.play_sine(1, 1000, self._output_dev)

    def handle_xtalk_right(self, *args):
        self.restore_configuration()
        self.ui.CallJSFunction('setMessage', _LABEL_PLAYTONE_RIGHT)
        self._ah.set_mixer_controls(self._mute_right_mixer_settings)
        self._ah.play_sine(0, 1000, self._output_dev)

    def listen_forever(self, sock):
        fd = sock.fileno()
        while True:
            _rl, _, _ = select.select([fd], [], [])
            if fd in _rl:
                conn, addr = sock.accept()
                self.handle_connection(conn)

    def start_server(self):
        '''
        Initialize server and start listening for external commands.
        '''
        sock = socket.socket()
        sock.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
        sock.bind((_HOST, _PORT))
        sock.listen(1)
        factory.console.info("Listening at port %d" % _PORT)

        self._listen_thread = threading.Thread(target=self.listen_forever,
                args=(sock,))
        self._listen_thread.start()

        self.ui.CallJSFunction('setMessage',
                'Ready for connection | 準备完成,等待链接')

    def unmute_speaker(self):
        self._ah.set_mixer_controls(self._unmute_speaker_mixer_settings)

    def on_test_complete(self):
        '''
        Restores the original state before exiting the test.
        '''
        utils.system('iptables -D INPUT -p tcp --dport %s -j ACCEPT' % _PORT)
        utils.system('ifconfig %s down' % self._eth)
        utils.system('ifconfig %s up' % self._eth)
        self.restore_configuration()
        self._ah.cleanup_deps(['sox', 'audioloop'])

    def check_eth_state(self):
        path = '/sys/class/net/%s/carrier' % self._eth
        output = None
        try:
            if os.path.exists(path):
                output = open(path).read()
        finally:
            if output:
                return output == '1\n'
            else:
                return False

    def test_command(self, event):
        factory.console.info('Get event %s' % event)
        cmd = event.data.get('cmd', '')
        for key in self._handlers.iterkeys():
            if key.match(cmd):
                self._handlers[key]()
                break

    def init_audio_server(self, event):
        self._eth = net_utils.FindUsableEthDevice()
        if not self._eth:
            raise error.TestError('No Ethernet interface available')
        factory.console.info('Got %s for connection' % self._eth)

        # Configure local network environment to accept command from test host.
        utils.system('ifconfig %s %s netmask 255.255.255.0 up' %
                (self._eth, _LOCAL_IP))
        utils.system('iptables -A INPUT -p tcp --dport %s -j ACCEPT' % _PORT)

        self.start_server()

    def run_once(self, input_dev='hw:0,0', output_dev='hw:0,0', eth='eth0',
            dmic_switch_mixer_settings=_DMIC_SWITCH_MIXER_SETTINGS,
            init_mixer_settings=_INIT_MIXER_SETTINGS,
            unmute_speaker_mixer_settings=_UNMUTE_SPEAKER_MIXER_SETTINGS,
            mute_right_mixer_settings=_MUTE_RIGHT_MIXER_SETTINGS,
            mute_left_mixer_settings=_MUTE_LEFT_MIXER_SETTINGS,
            use_sox_loop=False, use_multitone=False, loop_buffer_count=10):
        factory.console.info('%s run_once' % self.__class__)

        self._ah = audio_helper.AudioHelper(self)
        self._ah.setup_deps(['sox', 'audioloop'])
        self._detail_log = ''
        self._input_dev = input_dev
        self._output_dev = output_dev
        self._eth = None
        self._test_complete = False
        self._test_passed = False
        self._use_sox_loop = use_sox_loop
        self._use_multitone = use_multitone
        self._loop_buffer_count = loop_buffer_count

        self._multitone_job = None
        self._sweep_job = None
        self._tone_job = None
        self._loop_process = None

        # Mixer settings for different configurations.
        self._init_mixer_settings = init_mixer_settings
        self._unmute_speaker_mixer_settings = unmute_speaker_mixer_settings
        self._mute_left_mixer_settings = mute_left_mixer_settings
        self._mute_right_mixer_settings = mute_right_mixer_settings
        self._dmic_switch_mixer_settings = dmic_switch_mixer_settings

        self.ui = UI()

        # Register commands to corresponding handlers.
        self._handlers = {}
        self._handlers[_SEND_FILE_RE] = self.handle_send_file
        self._handlers[_RESULT_PASS_RE] = self.handle_result_pass
        self._handlers[_RESULT_FAIL_RE] = self.handle_result_fail
        self._handlers[_TEST_COMPLETE_RE] = self.handle_test_complete
        self._handlers[_LOOP_0_RE] = self.handle_loop_none
        self._handlers[_LOOP_1_RE] = self.handle_loop_from_dmic
        self._handlers[_LOOP_2_RE] = self.handle_loop_speaker_unmute
        self._handlers[_LOOP_3_RE] = self.handle_loop_jack
        self._handlers[_XTALK_L_RE] = self.handle_xtalk_left
        self._handlers[_XTALK_R_RE] = self.handle_xtalk_right
        self._handlers[_MULTITONE_RE] = self.handle_multitone
        self._handlers[_SWEEP_RE] = self.handle_sweep

        self.ui.AddEventHandler('init_audio_server', self.init_audio_server)
        self.ui.AddEventHandler('test_command', self.test_command)

        self.ui.Run()
