# Copyright 2016 The Chromium OS Authors. All rights reserved.
# Use of this source code is governed by a BSD-style license that can be
# found in the LICENSE file.


from autotest_lib.client.bin import test, utils
from autotest_lib.client.common_lib import error
from autotest_lib.client.cros.audio import alsa_utils


class audio_AlsaAPI(test.test):
    """Checks that simple ALSA API functions correctly."""
    version = 1


    def run_once(self, to_test):
        """Run alsa_api_test binary and verify its result.

        Checks the source code of alsa_api_test in audiotest repo for detail.

        @param to_test: support these test items:
                        move: Checks snd_pcm_forward API.
                        fill: Checks snd_pcm_mmap_begin API.
                        drop: Checks snd_pcm_drop API.
        """
        self._device = alsa_utils.get_sysdefault_playback_device()
        method_name = 'test_' + to_test
        method = getattr(self, method_name)
        method()


    def _make_alsa_api_test_command(self, option):
        """Makes command for alsa_api_test.

        @param option: same as to_test in run_once.

        @returns: The command in a list of args.
        """
        return ['alsa_api_test', '--device', self._device, '--%s' % option]


    def test_move(self):
        """Runs alsa_api_test command and checks the return code.

        Test snd_pcm_forward can move appl_ptr to hw_ptr.

        @raises error.TestError if command fails.
        """
        ret = utils.system(
                command=self._make_alsa_api_test_command('move'),
                ignore_status=True)
        if ret:
            raise error.TestError('ALSA API failed to move appl_ptr')


    def test_fill(self):
        """Runs alsa_api_test command and checks the return code.

        Test snd_pcm_mmap_begin can provide the access to the buffer, and memset
        can fill it with zeros without using snd_pcm_mmap_commit.

        @raises error.TestError if command fails.
        """
        ret = utils.system(
                command=self._make_alsa_api_test_command('fill'),
                ignore_status=True)
        if ret:
            raise error.TestError('ALSA API failed to fill buffer')


    def test_drop(self):
        """Runs alsa_api_test command and checks the return code.

        Test snd_pcm_drop can stop playback and reset hw_ptr to 0 in hardware.

        @raises error.TestError if command fails.
        """
        ret = utils.system(
                command=self._make_alsa_api_test_command('drop'),
                ignore_status=True)
        if ret:
            raise error.TestError(
                    'ALSA API failed to drop playback and reset hw_ptr')
