# Copyright (c) 2012 The Chromium OS Authors. All rights reserved.
# Use of this source code is governed by a BSD-style license that can be
# found in the LICENSE file.

import logging, os, re, urllib

from autotest_lib.client.cros import chrome_test
from autotest_lib.client.common_lib import error, utils

# See partner bug 891 for why these tests' performance is being ignored.
_IGNORE_PERFORMANCE_TESTS=(
    'tulip_hp.mp4',
    'tulip_bp.mp4',
    'tulip_mp.mp4')

class audiovideo_FFMPEG(chrome_test.ChromeBinaryTest):
    """
    This test plays the media from the URLs in the 'testcases' file and records
    frames per second and CPU usage measured.
    """
    version = 1
    test_binary = 'ffmpeg_tests'
    libffmpeg = 'libffmpegsumo.so'
    chrome_tst = '/usr/local/autotest/deps/chrome_test/test_src/out/Release/'
    chrome_sys = '/opt/google/chrome/'

    def run_once(self, fps_warning=0):
        """
        Run FFMPEG performance test!
        @param fps_warning: Emit warning when fps falls below this threshold.
        """
        # LD_LIBRARY_PATH does not work anymore - have to make a symlink.
        chrome_tst_libffmpeg = os.path.join(self.chrome_tst, self.libffmpeg)
        chrome_sys_libffmpeg = os.path.join(self.chrome_sys, self.libffmpeg)
        if not os.path.exists(chrome_tst_libffmpeg):
            os.symlink(chrome_sys_libffmpeg, chrome_tst_libffmpeg)

        # fetch all the test cases from file.
        testcases = os.path.join(self.bindir, 'testcases')
        self.performance_results = {}
        self.min_fps_video = 100
        self.max_tpf_audio = 0
        self._fps_warning = fps_warning

        for line in open(testcases, "rt"):
            # skip comment line and blank line
            line = line.rstrip()
            if len(line) == 0: continue
            if line[0] == "#": continue
            # run each test cases
            testcase = line.split()
            self.run_testcase(testcase)
        self.performance_results['fps_video_min'] = self.min_fps_video
        self.performance_results['tpf_audio_max'] = self.max_tpf_audio
        self.write_perf_keyval(self.performance_results)


    def run_testcase(self, testcase):
        """
        Runs a single tescase and records the CPU usage.
        @param testcase: URL with media file to play.
        """
        file_url = testcase[0]
        if file_url.startswith("http"):
            file_name = file_url.split('/')[-1]
            file_path = os.path.join(self.bindir, file_name)
            logging.info("Retrieving %s" % file_url)
            urllib.urlretrieve(file_url, file_path)
            logging.info("Done.")
        else:
            # if url is local, we assume it is in the same directory.
            file_name = file_url;
            file_path = os.path.join(self.bindir, file_name)

        if not os.path.exists(file_path):
            raise error.TestError('ffmpeg_tests: test media missing %s!'
                                  % file_url)
        executable = os.path.join(self.chrome_tst, self.test_binary)
        # TODO(ihf): There used to be a LD_LIBRARY_PATH=/opt/google/chrome/
        # in the command_line. Investigate why it stopped working.
        command_line = ('%s %s'
                        % (executable, file_path))
        logging.info('Running %s' % command_line)
        cpu_usage, stdout = utils.get_cpu_percentage(
                                 utils.system_output,
                                 command_line,
                                 retain_output=True)

        cpu_usage *= 100.0  # in percentage.

        # what's the fps we measure for video.
        fps_pattern = re.search(r"FPS:\s+([\d\.]+)", stdout)
        # what's the time per frame for audio.
        tpf_pattern = re.search(r"TIME PER FRAME \(MS\):\s+([\d\.]+)", stdout)
        if fps_pattern:
            fps = float(fps_pattern.group(1))
            logging.info("CPU Usage %s%%; FPS: %s (%s)" % (cpu_usage, fps,
                                                           file_name))
            if not file_name in _IGNORE_PERFORMANCE_TESTS:
                self.min_fps_video = min(self.min_fps_video, fps);
            if fps < self._fps_warning:
                self.job.record('WARN', None, 'FPS Warning',
                                '%s had fps %g < %g' %
                                (file_url, fps, self._fps_warning))
            # record the performance data for future analysis.
            namekey = file_name.lower().replace('.', '_')
            self.performance_results['fps_' + namekey] = fps
            self.performance_results['cpuusage_' + namekey] = cpu_usage
        elif tpf_pattern:
            tpf = float(tpf_pattern.group(1))
            self.max_tpf_audio = max(self.max_tpf_audio, tpf);
            logging.info("CPU Usage %s%%; TimePerFrame: %s" % (cpu_usage, tpf))
            # record the performance data for future analysis.
            namekey = file_name.lower().replace('.', '_')
            self.performance_results['timeperframe_' + namekey] = tpf
            self.performance_results['cpuusage_' + namekey] = cpu_usage
        else:
            raise error.TestFail("ffmpeg_tests failed to exit normally!")

        # TODO(jiesun/fbarchard): what else need to be checked?

        # remove file after test to save diskspace.
        os.remove(file_path);
