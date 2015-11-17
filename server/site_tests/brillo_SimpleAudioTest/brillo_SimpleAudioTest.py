# Copyright 2015 The Chromium OS Authors. All rights reserved.
# Use of this source code is governed by a BSD-style license that can be
# found in the LICENSE file.

import logging
import os
import struct
import time
import wave

from autotest_lib.client.common_lib import error
from autotest_lib.server import test


# Num of channels to record.
_NUM_CHANNELS = 1
# Recording sample rate 48kHz.
_SAMPLE_RATE = 48000
# Recording sample format is signed 16-bit PCM. Size is 2 bytes.
_SAMPLE_WIDTH = 2

_AUDIO_POLICY_DEFAULT_OUTPUT_DEVICE = 'default_output_device'
_AUDIO_POLICY_ATTACHED_OUTPUT_DEVICES = 'attached_output_devices'
_WIRED_HEADSET = 'AUDIO_DEVICE_OUT_WIRED_HEADSET'

_DUT_AUDIO_POLICY_PATH = 'system/etc/audio_policy.conf'
_ORIGINAL_AUDIO_POLICY_FILENAME = 'audio_policy.original.conf'
_TEST_AUDIO_POLICY_FILENAME = 'audio_policy.test.conf'
_REC_FILENAME = 'rec_file.wav'
_SCRIPT_FILENAME = 'script'

class brillo_SimpleAudioTest(test.test):
    """Verify that basic audio playback and recording works."""
    version = 1


    def push_file_to_system(self, host, local_filename, dut_filename):
        """Push a file to the system partition.

        This requires us to restart adbd as root, remount the device, then push
        the file to the device.

        @param host: A host object representing the dut.
        @param local_filename: A path to the file on the host.
        @param dut_filename: A path to the file on the DUT.
        """
        host.adb_run('root')
        time.sleep(10)
        host.adb_run('wait-for-device')
        host.adb_run('remount')
        host.send_file(local_filename, dut_filename, True)


    def update_policy(self, host):
        """Updates the audio_policy.conf file to use headphone jack.

        Currently, there's no way to update the audio routing if a headset is
        plugged in. This function manually changes the audio routing to play
        through the headset.
        TODO(ralphnathan): Remove this once b/25188354 is resolved.

        @param host: A host object representing the DUT.

        @raise test.testError: Something went wrong while trying to update the
                               audio policy file.
        """
        self.original_audio_policy_filename = os.path.join(
                self.tmpdir, _ORIGINAL_AUDIO_POLICY_FILENAME)
        host.get_file(_DUT_AUDIO_POLICY_PATH,
                      self.original_audio_policy_filename, True)
        test_audio_policy_filename = os.path.join(
                self.tmpdir, _TEST_AUDIO_POLICY_FILENAME)
        with open(self.original_audio_policy_filename, 'r') as original_conf:
            with open(test_audio_policy_filename, 'w') as test_conf:
                for line in original_conf:
                    if (_AUDIO_POLICY_ATTACHED_OUTPUT_DEVICES in line and
                        _WIRED_HEADSET not in line):
                        line = '%s|%s\n' % (line.rstrip(), _WIRED_HEADSET)
                    elif _AUDIO_POLICY_DEFAULT_OUTPUT_DEVICE in line:
                        line = '%s %s\n' % (_AUDIO_POLICY_DEFAULT_OUTPUT_DEVICE,
                                            _WIRED_HEADSET)
                    test_conf.write(line)
        self.push_file_to_system(
                host, test_audio_policy_filename, _DUT_AUDIO_POLICY_PATH)


    def run_command_in_script(self, host, cmd):
        """Write cmd to a script and run it.

        @param host: A object representing the DUT.
        @param cmd: The command to write to run.
        """
        local_script_filename = os.path.join(
                self.tmpdir, _SCRIPT_FILENAME)
        with open(local_script_filename, 'w') as local_script_file:
            local_script_file.write(cmd)
        dut_script_filename = os.path.join(self.dut_temp_dir, _SCRIPT_FILENAME);
        host.send_file(local_script_filename, dut_script_filename, True)
        host.run('chmod 777 %s && ./%s' % (dut_script_filename,
                                           dut_script_filename))


    def get_abs_highest_peak(self, wav_filename):
        """Open a wav file and get the highest/lowest peak value.

        @param wav_filename: Input .wav file to analyze.

        @return The absolute maximum PCM value in the .wav file.
        """
        chk_file = wave.open(wav_filename, 'r')
        if chk_file.getnchannels() != _NUM_CHANNELS:
            raise error.TestError('Incorrect number of channels.')
        if chk_file.getsampwidth() != _SAMPLE_WIDTH:
            raise error.TestError('Incorrect sample width')
        if chk_file.getframerate() != _SAMPLE_RATE:
            raise error.TestError('Incorrect sample rate')
        frames = struct.unpack('%ih' % chk_file.getnframes(),
                               chk_file.readframes(chk_file.getnframes()))
        return max(abs(i) for i in frames)


    def cleanup(self, host):
      """Returns the audio_policy.conf file to its original state.

      @param host: A host object representing the DUT.
      """
      self.push_file_to_system(host, self.original_audio_policy_filename,
                               _DUT_AUDIO_POLICY_PATH)


    def run_once(self, host=None):
        """Runs the test.

        @param host: A host object representing the DUT.

        @raise TestError: Something went wrong while trying to execute the test.
        @raise TestFail: The test failed.
        """
        logging.info('Updating audio_policy.conf for testing.')
        try:
            self.update_policy(host)
            host.reboot()
        except error.AutoservRunError:
            error.TestFail(
                    'Could not reboot the DUT with wired headset as default '
                    'output device in the test audio_policy.conf.')
            self.cleanup(host)

        logging.info('Recording background noise.')
        try:
            self.dut_temp_dir = host.get_tmp_dir()
            dut_rec_filename = os.path.join(self.dut_temp_dir, _REC_FILENAME)
            cmd = 'su root slesTest_recBuffQueue ' + dut_rec_filename
            self.run_command_in_script(host, cmd)
            threshold_file_local = os.path.join(self.tmpdir,
                                                'threshold_file.wav')
            host.get_file(dut_rec_filename, threshold_file_local, True)
            threshold = self.get_abs_highest_peak(threshold_file_local)
            # Calculate one percent of max volume. Note that the date format is
            # signed 16-bit PCM.
            one_percent_max_volume = (pow(2, _SAMPLE_WIDTH * 8 - 1) - 1) / 100
            # If the threshold is greater than 1% of max value without playing
            # audio, that means there's too much noise (audio or electrical).
            if threshold > one_percent_max_volume:
                raise error.TestError('Environment is too noisy.')
            # Multiply the threshold by a factor of 10 so the recorded data has
            # to exceed 10% of the max value. If the threshold is 0, set it to
            # 1% of the max value.
            if threshold:
                threshold *= 10;
            else:
                threshold = one_percent_max_volume
        except wave.Error:
            raise error.TestError(
                    'Error reading the backgroud noise recording wav file.')
        except error.AutoservRunError:
            raise error.TestFail('Error recording audio to establish '
                                 'background noise threshold.')
            self.cleanup(host)

        logging.info('Performing test.')
        try:
            cmd += ' & su root slesTest_sawtoothBufferQueue & wait'
            self.run_command_in_script(host, cmd)
            local_rec_filename = os.path.join(
                    self.tmpdir, _REC_FILENAME)
            host.get_file(dut_rec_filename, local_rec_filename, True)
            rec_max_value = self.get_abs_highest_peak(local_rec_filename)
            if rec_max_value < threshold:
                logging.info(
                        'Peak of recorded data is %i while threshold is %i.',
                        rec_max_value, threshold);
                raise error.TestFail(
                        'The recorded audio level is below the expected '
                        'threshold. This might be that playback did not '
                        'produce the expected output, or that recording did '
                        'not capture the produced output. Check the audio '
                        'connections on the DUT.')
        except wave.Error:
            raise error.TestError(
                    'Error reading the playback recording wav file.')
        except error.AutoservRunError:
            raise error.TestFail(
                    'Error executing audio play and record commands.');
        finally:
              self.cleanup(host)
