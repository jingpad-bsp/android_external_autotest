# Copyright 2016 The Chromium OS Authors. All rights reserved.
# Use of this source code is governed by a BSD-style license that can be
# found in the LICENSE file.

"""Feedback implementation for audio with closed-loop cable."""

import logging
import os
import tempfile

import common
from autotest_lib.client.common_lib import error
from autotest_lib.client.common_lib import site_utils
from autotest_lib.client.common_lib.feedback import client
from autotest_lib.server.brillo import host_utils


def _max_volume(sample_width):
    """Returns the maximum possible volume.

    This is the highest absolute value of a signed integer of a given width.

    @param sample_width: The sample width in bytes.
    """
    return (1 << (sample_width * 8 - 1))


# Constants used for updating the audio policy.
#
_DUT_AUDIO_POLICY_PATH = 'system/etc/audio_policy.conf'
_AUDIO_POLICY_ATTACHED_INPUT_DEVICES = 'attached_input_devices'
_AUDIO_POLICY_ATTACHED_OUTPUT_DEVICES = 'attached_output_devices'
_AUDIO_POLICY_DEFAULT_OUTPUT_DEVICE = 'default_output_device'
_WIRED_HEADSET_IN = 'AUDIO_DEVICE_IN_WIRED_HEADSET'
_WIRED_HEADSET_OUT = 'AUDIO_DEVICE_OUT_WIRED_HEADSET'

# Constants used when recording playback.
#
_REC_FILENAME = 'rec_file.wav'
_REC_DURATION = 10
# Number of channels to record.
_NUM_CHANNELS = 1
# Recording sample rate (48kHz).
_SAMPLE_RATE = 48000
# Recording sample format is signed 16-bit PCM (two bytes).
_SAMPLE_WIDTH = 2
# The peak when recording silence is 5% of the max volume.
_SILENCE_MAX = _max_volume(_SAMPLE_WIDTH) / 20


class Client(client.Client):
    """Audio closed-loop feedback implementation.

    This class (and the queries it instantiates) perform playback and recording
    of audio on the DUT itself, with the assumption that the audio in/out
    connections are cross-wired with a cable. It provides some shared logic
    that queries can use for handling the DUT as well as maintaining shared
    state between queries (such as an audible volume threshold).
    """

    def __init__(self):
        """Construct the client library."""
        super(Client, self).__init__()
        self.host = None
        self.dut_tmp_dir = None
        self.tmp_dir = None
        self.orig_policy = None
        # By default, the audible threshold is equivalent to the silence cap.
        self.audible_threshold = _SILENCE_MAX


    def set_audible_threshold(self, threshold):
        """Sets the audible volume threshold.

        @param threshold: New threshold value.
        """
        self.audible_threshold = threshold


    def _patch_audio_policy(self):
        """Updates the audio_policy.conf file to use the headphone jack.

        Currently, there's no way to update the audio routing if a headset is
        plugged in. This function manually changes the audio routing to play
        through the headset.
        TODO(ralphnathan): Remove this once b/25188354 is resolved.
        """
        # Fetch the DUT's original audio policy.
        _, self.orig_policy = tempfile.mkstemp(dir=self.tmp_dir)
        self.host.get_file(_DUT_AUDIO_POLICY_PATH, self.orig_policy,
                           delete_dest=True)

        # Patch the policy to route audio to a headset.
        _, test_policy = tempfile.mkstemp(dir=self.tmp_dir)
        policy_changed = False
        with open(self.orig_policy) as orig_file:
            with open(test_policy, 'w') as test_file:
                for line in orig_file:
                    if _WIRED_HEADSET_OUT not in line:
                        if _AUDIO_POLICY_ATTACHED_OUTPUT_DEVICES in line:
                            line = '%s|%s\n' % (line.rstrip(),
                                                _WIRED_HEADSET_OUT)
                            policy_changed = True
                        elif _AUDIO_POLICY_DEFAULT_OUTPUT_DEVICE in line:
                            line = '%s %s\n' % (line.rstrip().rsplit(' ', 1)[0],
                                                _WIRED_HEADSET_OUT)
                            policy_changed = True
                    if _WIRED_HEADSET_IN not in line:
                        if _AUDIO_POLICY_ATTACHED_INPUT_DEVICES in line:
                            line = '%s|%s\n' % (line.rstrip(), _WIRED_HEADSET_IN)
                            policy_changed = True

                    test_file.write(line)

        # Update the DUT's audio policy if changed.
        if policy_changed:
            logging.info('Updating audio policy to route audio to headset')
            self.host.remount()
            self.host.send_file(test_policy, _DUT_AUDIO_POLICY_PATH,
                                delete_dest=True)
            self.host.reboot()
        else:
            os.remove(self.orig_policy)
            self.orig_policy = None

        os.remove(test_policy)


    # Interface overrides.
    #
    def _initialize_impl(self, test, host):
        """Initializes the feedback object.

        @param test: An object representing the test case.
        @param host: An object representing the DUT.
        """
        self.host = host
        self.tmp_dir = test.tmpdir
        self.dut_tmp_dir = host.get_tmp_dir()
        self._patch_audio_policy()


    def _finalize_impl(self):
        """Finalizes the feedback object."""
        if self.orig_policy:
            logging.info('Restoring DUT audio policy')
            self.host.remount()
            self.host.send_file(self.orig_policy, _DUT_AUDIO_POLICY_PATH,
                                delete_dest=True)
            os.remove(self.orig_policy)
            self.orig_policy = None


    def _new_query_impl(self, query_id):
        """Instantiates a new query.

        @param query_id: A query identifier.

        @return A query object.

        @raise error.TestError: Query is not supported.
        """
        if query_id == client.QUERY_AUDIO_PLAYBACK_SILENT:
            return SilentPlaybackAudioQuery(self)
        elif query_id == client.QUERY_AUDIO_PLAYBACK_AUDIBLE:
            return AudiblePlaybackAudioQuery(self)
        elif query_id == client.QUERY_AUDIO_RECORDING:
            return RecordingAudioQuery(self)
        else:
            raise error.TestError('Unsupported query (%s)' % query_id)


class _PlaybackAudioQuery(client.OutputQuery):
    """Playback query base class."""

    def __init__(self, client):
        """Constructor.

        @param client: The instantiating client object.
        """
        super(_PlaybackAudioQuery, self).__init__()
        self.client = client
        self.dut_rec_filename = None
        self.local_tmp_dir = None
        self.recording_pid = None


    def _process_recording(self):
        """Waits for recording to finish and processes the result.

        @return A list of the highest recorded peak value for each channel.

        @raise error.TestError: Error while validating the recording.
        @raise error.TestFail: Recording file failed to validate.
        """
        # Wait for recording to finish.
        timeout = _REC_DURATION + 5
        if not host_utils.wait_for_process(self.client.host,
                                           self.recording_pid, timeout):
            raise error.TestError(
                    'Recording did not terminate within %d seconds' % timeout)

        _, local_rec_filename = tempfile.mkstemp(
                prefix='recording-', suffix='.wav', dir=self.local_tmp_dir)
        try:
            self.client.host.get_file(self.dut_rec_filename,
                                      local_rec_filename, delete_dest=True)
            return site_utils.check_wav_file(local_rec_filename,
                                             num_channels=_NUM_CHANNELS,
                                             sample_rate=_SAMPLE_RATE,
                                             sample_width=_SAMPLE_WIDTH)
        except ValueError as e:
            raise error.TestFail('Invalid file attributes: %s' % e)


    # Implementation overrides.
    #
    def _prepare_impl(self):
        """Implementation of query preparation logic."""
        self.dut_rec_filename = os.path.join(self.client.dut_tmp_dir,
                                             _REC_FILENAME)
        self.local_tmp_dir = tempfile.mkdtemp(dir=self.client.tmp_dir)

        # Trigger recording in the background.
        # TODO(garnold) Remove 'su root' once b/25663983 is resolved.
        cmd = ('su root slesTest_recBuffQueue -d%d %s' %
               (_REC_DURATION, self.dut_rec_filename))
        self.recording_pid = host_utils.run_in_background(self.client.host, cmd)


class SilentPlaybackAudioQuery(_PlaybackAudioQuery):
    """Implementation of a silent playback query."""

    def __init__(self, client):
        super(SilentPlaybackAudioQuery, self).__init__(client)


    # Implementation overrides.
    #
    def _validate_impl(self):
        """Implementation of query validation logic."""
        silence_peaks = self._process_recording()
        silence_peak = max(silence_peaks)
        # Fail if the silence peak volume exceeds the maximum allowed.
        if silence_peak > _SILENCE_MAX:
            logging.error('Silence peak level (%d) exceeds the max allowed (%d)',
                          silence_peak, _SILENCE_MAX)
            raise error.TestFail('Environment is too noisy')

        # Update the client audible threshold, if so instructed.
        audible_threshold = silence_peak * 15
        logging.info('Silent peak level (%d) is below the max allowed (%d); '
                     'setting audible threshold to %d',
                     silence_peak, _SILENCE_MAX, audible_threshold)
        self.client.set_audible_threshold(audible_threshold)


class AudiblePlaybackAudioQuery(_PlaybackAudioQuery):
    """Implementation of an audible playback query."""

    def __init__(self, client):
        super(AudiblePlaybackAudioQuery, self).__init__(client)


    # Implementation overrides.
    #
    def _validate_impl(self, audio_file=None):
        """Implementation of query validation logic."""
        # TODO(garnold) This currently ignores the audio_file argument entirely
        # and just ensures that peak levels look reasonable. We should probably
        # compare actual audio content.

        # Ensure that peak recording volume exceeds the threshold.
        audible_peaks = self._process_recording()
        min_channel, min_audible_peak = min(enumerate(audible_peaks),
                                            key=lambda p: p[1])
        if min_audible_peak < self.client.audible_threshold:
            logging.error(
                    'Audible peak level (%d) is less than expected (%d) for '
                    'channel %d', min_audible_peak,
                    self.client.audible_threshold, min_channel)
            raise error.TestFail(
                    'The played audio peak level is below the expected '
                    'threshold. Either playback did not work, or the volume '
                    'level is too low. Check the audio connections and '
                    'settings on the DUT.')

        logging.info('Audible peak level (%d) exceeds the threshold (%d)',
                     min_audible_peak, self.client.audible_threshold)


class RecordingAudioQuery(client.InputQuery):
    """Implementation of a recording query."""

    def __init__(self, client):
        super(RecordingAudioQuery, self).__init__()
        self.client = client


    def _prepare_impl(self):
        """Implementation of query preparation logic (no-op)."""
        pass


    def _emit_impl(self):
        """Implementation of query emission logic."""
        self.client.host.run('slesTest_sawtoothBufferQueue')


    def _validate_impl(self, captured_audio_file, sample_width,
                       sample_rate=None, num_channels=None,
                       peak_percent_min=1, peak_percent_max=100):
        """Implementation of query validation logic.

        @param captured_audio_file: Path to the recorded WAV file.
        @peak_percent_min: Lower bound on peak recorded volume as percentage of
            max molume (0-100). Default is 1%.
        @peak_percent_max: Upper bound on peak recorded volume as percentage of
            max molume (0-100). Default is 100% (no limit).
        """
        # TODO(garnold) Currently, we just test whether anything audible was
        # recorded. We should compare the captured audio to the one produced.
        try:
            recorded_peaks = site_utils.check_wav_file(
                    captured_audio_file, num_channels=num_channels,
                    sample_rate=sample_rate, sample_width=sample_width)
        except ValueError as e:
            raise error.TestFail('Recorded audio file is invalid: %s' % e)

        max_volume = _max_volume(sample_width)
        peak_min = max_volume * peak_percent_min / 100
        peak_max = max_volume * peak_percent_max / 100
        for channel, recorded_peak in enumerate(recorded_peaks):
            if recorded_peak < peak_min:
                logging.error(
                        'Recorded audio peak level (%d) is less than expected '
                        '(%d) for channel %d', recorded_peak, peak_min, channel)
                raise error.TestFail(
                        'The recorded audio peak level is below the expected '
                        'threshold. Either recording did not capture the '
                        'produced audio, or the recording level is too low. '
                        'Check the audio connections and settings on the DUT.')

            if recorded_peak > peak_max:
                logging.error(
                        'Recorded audio peak level (%d) is more than expected '
                        '(%d) for channel %d', recorded_peak, peak_max, channel)
                raise error.TestFail(
                        'The recorded audio peak level exceeds the expected '
                        'maximum. Either recording captured much background '
                        'noise, or the recording level is too high. Check the '
                        'audio connections and settings on the DUT.')
