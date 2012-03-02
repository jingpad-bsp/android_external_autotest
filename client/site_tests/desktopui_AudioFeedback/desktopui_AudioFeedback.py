# Copyright (c) 2012 The Chromium Authors. All rights reserved.
# Use of this source code is governed by a BSD-style license that can be
# found in the LICENSE file.

import logging, os, re, threading, utils

from autotest_lib.client.bin import test, utils
from autotest_lib.client.common_lib import error
from autotest_lib.client.cros import cros_ui_test, httpd

# Names of mixer controls.
_CONTROL_MASTER = "'Master Playback Volume'"
_CONTROL_HEADPHONE = "'Headphone Playback Volume'"
_CONTROL_SPEAKER = "'Speaker Playback Volume'"
_CONTROL_SPEAKER_HP = "'HP/Speakers'"
_CONTROL_MIC_BOOST = "'Mic Boost Volume'"
_CONTROL_CAPTURE = "'Capture Volume'"
_CONTROL_PCM = "'PCM Playback Volume'"
_CONTROL_DIGITAL = "'Digital Capture Volume'"
_CONTROL_CAPTURE_SWITCH = "'Capture Switch'"

# Default test configuration.
_DEFAULT_CARD = '0'
_DEFAULT_FREQUENCY = 1000
_DEFAULT_MIXER_SETTINGS = [{'name': _CONTROL_MASTER, 'value': "100%"},
                           {'name': _CONTROL_HEADPHONE, 'value': "100%"},
                           {'name': _CONTROL_MIC_BOOST, 'value': "50%"},
                           {'name': _CONTROL_PCM, 'value': "100%"},
                           {'name': _CONTROL_DIGITAL, 'value': "100%"},
                           {'name': _CONTROL_CAPTURE, 'value': "100%"},
                           {'name': _CONTROL_CAPTURE_SWITCH, 'value': "on"}]

_CONTROL_SPEAKER_DEVICE = ['x86-alex', 'x86-mario', 'x86-zgb']
_CONTROL_SPEAKER_DEVICE_HP = ['stumpy', 'lumpy']

_DEFAULT_NUM_CHANNELS = 2
_DEFAULT_RECORD_DURATION = 15
# Minimum RMS value to consider a "pass".
_DEFAULT_SOX_RMS_THRESHOLD = 0.30

# Regexp parsing sox output.
_SOX_RMS_AMPLITUDE_RE = re.compile('RMS\s+amplitude:\s+(.+)')
# Format used in sox commands.
_SOX_FORMAT = '-t raw -b 16 -e signed -r 48000 -L'


class RecordSampleThread(threading.Thread):
    """Wraps the execution of arecord in a thread."""
    def __init__(self, audio, duration, recordfile):
        threading.Thread.__init__(self)
        self._audio = audio
        self._duration = duration
        self._recordfile = recordfile

    def run(self):
        self._audio.record_sample(self._duration, self._recordfile)


class desktopui_AudioFeedback(cros_ui_test.UITest):
    version = 1

    def setup(self):
        self.job.setup_dep(['test_tones'])
        self.job.setup_dep(['sox'])

    def initialize(self,
                   card=_DEFAULT_CARD,
                   frequency=_DEFAULT_FREQUENCY,
                   mixer_settings=_DEFAULT_MIXER_SETTINGS,
                   num_channels=_DEFAULT_NUM_CHANNELS,
                   record_duration=_DEFAULT_RECORD_DURATION,
                   sox_min_rms=_DEFAULT_SOX_RMS_THRESHOLD):
        """Setup the deps for the test.

        Args:
            card: The index of the sound card to use.
            frequency: The frequency of the test tone that is looped back.
            mixer_settings: Alsa control settings to apply to the mixer before
                starting the test.
            num_channels: The number of channels on the device to test.
            record_duration: How long of a sample to record.
            sox_min_rms: The minimum RMS value to consider a pass.

        Raises:
            error.TestError if the deps can't be run.
        """
        self._card = card
        self._frequency = frequency
        self._mixer_settings = mixer_settings
        self._num_channels = num_channels
        self._record_duration = record_duration
        self._sox_min_rms = sox_min_rms

        dep = 'sox'
        dep_dir = os.path.join(self.autodir, 'deps', dep)
        self.job.install_pkg(dep, 'dep', dep_dir)
        self._sox_path = os.path.join(dep_dir, 'bin', dep)
        self._sox_lib_path = os.path.join(dep_dir, 'lib')
        if not (os.path.exists(self._sox_path) and
                os.access(self._sox_path, os.X_OK)):
            raise error.TestError(
                '%s is not an executable' % self._sox_path)

        super(desktopui_AudioFeedback, self).initialize()
        self._test_url = 'http://localhost:8000/youtube.html'
        self._testServer = httpd.HTTPListener(8000, docroot=self.bindir)
        self._testServer.run()

    def run_once(self):
        self.set_mixer_controls()
        noise_file = os.path.join(self.tmpdir, os.tmpnam())
        logging.info('Noise file: %s' % noise_file)
        self.record_sample(_DEFAULT_RECORD_DURATION, noise_file)
        try:
            for channel in xrange(0, self._num_channels):
                self.loopback_test_one_channel(channel, noise_file)
        finally:
            if os.path.isfile(noise_file):
                os.unlink(noise_file)

    def play_video(self):
        """Plays a Youtube video to record audio samples.

           Skipping initial 60 seconds so we can ignore initial silence
           in the video.
        """
        logging.info('Playing back youtube media file %s.' % self._test_url)
        self.pyauto.NavigateToURL(self._test_url)
        if not self.pyauto.WaitUntil(lambda: self.pyauto.ExecuteJavascript("""
                    player_status = document.getElementById('player_status');
                    window.domAutomationController.send(player_status.innerHTML);
               """), expect_retval='player ready'):
            raise error.TestError('Failed to load the Youtube player')
        self.pyauto.ExecuteJavascript("""
            ytplayer.pauseVideo();
            ytplayer.seekTo(60, true);
            ytplayer.playVideo();
            window.domAutomationController.send('');
        """)

    def loopback_test_one_channel(self, channel, noise_file):
        """Test loopback for a given channel.

        Args:
            channel: The channel to test loopback on.
            noise_file: Noise profile to use for filtering, None to skip noise
                filtering.
        """
        tmpfile = os.path.join(self.tmpdir, os.tmpnam())
        record_thread = RecordSampleThread(self, self._record_duration, tmpfile)
        self.play_video()
        record_thread.start()
        record_thread.join()

        if noise_file is not None:
            test_file = self.noise_reduce_file(tmpfile, noise_file)
            os.unlink(tmpfile)
        else:
            test_file = tmpfile
        try:
            self.check_recorded_audio(test_file, channel)
        finally:
            if os.path.isfile(test_file):
                os.unlink(test_file)

    def record_sample(self, duration, tmpfile):
        """Records a sample from the default input device.

        Args:
            duration: How long to record in seconds.
            tmpfile: The file to record to.
        """
        cmd_rec = 'arecord -d %f -f dat %s' % (duration, tmpfile)
        logging.info('Recording audio now for %f seconds.' % duration)
        utils.system(cmd_rec)

    def set_mixer_controls(self):
        """Sets all mixer controls listed in the mixer settings on card."""
        logging.info('Setting mixer control values on %s' % self._card)

        # Speaker control settings may differ from device to device.
        if self.pyauto.ChromeOSBoard() in _CONTROL_SPEAKER_DEVICE:
            self._mixer_settings.append({'name': _CONTROL_SPEAKER,
                                         'value': "0%"})
        elif self.pyauto.ChromeOSBoard() in _CONTROL_SPEAKER_DEVICE_HP:
            self._mixer_settings.append({'name': _CONTROL_SPEAKER_HP,
                                         'value': "0%"})

        for item in self._mixer_settings:
            logging.info('Setting %s to %s on card %s' %
                         (item['name'], item['value'], self._card))
            cmd = 'amixer -c %s cset name=%s %s'
            cmd = cmd % (self._card, item['name'], item['value'])
            try:
                utils.system(cmd)
            except error.CmdError:
                # A card is allowed to not support all the controls, so don't
                # fail the test here if we get an error.
                logging.info('amixer command failed: %s' % cmd)

    def check_recorded_audio(self, infile, channel):
        """Runs the sox command to check if we captured audio.

        Note: if we captured any sufficient loud audio which can generate
        the rms_value greater than the threshold value, test will pass.
        TODO (rohitbm) : find a way to compare the recorded audio with
                         an actual sample file.

        Args:
            infile: The file is to test for (strong) audio content via the RMS
                    method.
            channel: The audio channel to test.

        Raises:
            error.TestFail if the RMS amplitude of the recording isn't above
                the threshold.
        """
        # Build up a pan value string for the sox command.
        pan_values = '1' if channel == 0 else '0'
        for pan_index in range(1, self._num_channels):
            if channel == pan_index:
                pan_values += ',1'
            else:
                pan_values += ',0'
        # Set up the sox commands.
        os.environ['LD_LIBRARY_PATH'] = self._sox_lib_path
        sox_mixer_cmd = '%s -c 2 %s %s -c 1 %s - mixer %s'
        sox_mixer_cmd = sox_mixer_cmd % (self._sox_path, _SOX_FORMAT, infile,
                                         _SOX_FORMAT, pan_values)
        stat_cmd = '%s -c 1 %s - -n stat 2>&1' % (self._sox_path, _SOX_FORMAT)
        sox_cmd = '%s | %s' % (sox_mixer_cmd, stat_cmd)
        logging.info('running %s' % sox_cmd)
        sox_output = utils.system_output(sox_cmd, retain_output=True)
        # Find the RMS value line and check that it is above threshold.
        sox_rms_status = False
        for rms_line in sox_output.split('\n'):
            m = _SOX_RMS_AMPLITUDE_RE.match(rms_line)
            if m is not None:
                sox_rms_status = True
                rms_val = float(m.group(1))
                logging.info('Got audio RMS value of %f. Minimum pass is %f.' %
                             (rms_val, self._sox_min_rms))
                if rms_val < self._sox_min_rms:
                    raise error.TestError(
                        'Audio RMS value %f too low. Minimum pass is %f.' %
                        (rms_val, self._sox_min_rms))
        # In case sox didn't return an RMS value.
        if not sox_rms_status:
            raise error.TestError(
                'Failed to generate an audio RMS value from playback.')

    def noise_reduce_file(self, test_file, noise_file):
        """Runs the sox command to reduce the noise.

        Performs noise reduction on test_file using the noise profile from
        noise_file.

        Args:
            test_file: The file to noise reduce.
            noise_file: The file containing the noise profile.
                        This can be created by recording silence.

        Returns:
            The name of the file containing the noise-reduced data.
        """
        out_file = os.path.join(self.tmpdir, os.tmpnam())
        os.environ['LD_LIBRARY_PATH'] = self._sox_lib_path
        prof_cmd = '%s -c 2 %s %s -n noiseprof' % (self._sox_path,
                                                   _SOX_FORMAT,
                                                   noise_file)
        reduce_cmd = ('%s -c 2 %s %s -c 2 %s %s noisered' %
                          (self._sox_path, _SOX_FORMAT, test_file, _SOX_FORMAT,
                           out_file))
        utils.system('%s | %s' % (prof_cmd, reduce_cmd))
        return out_file
