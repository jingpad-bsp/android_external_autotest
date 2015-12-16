# Copyright 2016 The Chromium OS Authors. All rights reserved.
# Use of this source code is governed by a BSD-style license that can be
# found in the LICENSE file.

import logging
import os
import tempfile

import common
from autotest_lib.client.common_lib import error
from autotest_lib.client.common_lib.feedback import client
from autotest_lib.server import test
from autotest_lib.server.brillo import host_utils


# Number of channels to record.
_NUM_CHANNELS = 1
# Recording sample rate (48kHz).
_SAMPLE_RATE = 48000
# Recording sample format is signed 16-bit PCM (two bytes).
_SAMPLE_WIDTH = 2

_REC_FILENAME = 'rec_file.wav'
_REC_DURATION_SECS = 10

class brillo_RecordingAudioTest(test.test):
    """Verify that audio recording works."""
    version = 1


    def __init__(self, *args, **kwargs):
        super(brillo_RecordingAudioTest, self).__init__(*args, **kwargs)
        self.host = None


    def test_recording(self, fb_query):
        """Performs a recording test.

        @param fb_query: A feedback query.

        @raise error.TestError: An error occurred while executing the test.
        @raise error.TestFail: The test failed.
        """
        dut_tmpdir = self.host.get_tmp_dir()
        dut_rec_file = os.path.join(dut_tmpdir, _REC_FILENAME)
        # TODO(garnold) Remove 'su root' once b/25663983 is resolved.
        cmd = ('su root slesTest_recBuffQueue -d%d %s' %
               (_REC_DURATION_SECS, dut_rec_file))
        timeout = _REC_DURATION_SECS + 5
        fb_query.prepare()
        logging.info('Beginning audio recording')
        pid = host_utils.run_in_background(self.host, cmd)
        logging.info('Requesting audio input')
        fb_query.emit()
        logging.info('Waiting for recording to terminate')
        if not host_utils.wait_for_process(self.host, pid, timeout):
            raise error.TestError(
                    'Recording did not terminate within %d seconds' % timeout)
        _, local_rec_file = tempfile.mkstemp(prefix='recording-',
                                             suffix='.wav', dir=self.tmpdir)
        self.host.get_file(dut_rec_file, local_rec_file, delete_dest=True)
        logging.info('Validating recorded audio')
        fb_query.validate(captured_audio_file=local_rec_file,
                          sample_width=_SAMPLE_WIDTH,
                          sample_rate=_SAMPLE_RATE,
                          num_channels=_NUM_CHANNELS)


    def run_once(self, host, fb_client):
        """Runs the test.

        @param host: A host object representing the DUT.
        @param fb_client: A feedback client implementation.

        @raise TestError: Something went wrong while trying to execute the test.
        @raise TestFail: The test failed.
        """
        self.host = host
        with fb_client.initialize(self, host):
            fb_query = fb_client.new_query(client.QUERY_AUDIO_RECORDING)
            self.test_recording(fb_query)
