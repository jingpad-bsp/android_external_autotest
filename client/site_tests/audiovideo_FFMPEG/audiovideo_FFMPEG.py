# Copyright (c) 2010 The Chromium OS Authors. All rights reserved.
# Use of this source code is governed by a BSD-style license that can be
# found in the LICENSE file.

import glob, logging, os, re, shutil, stat, string, time, urllib

from autotest_lib.client.bin import test
from autotest_lib.client.common_lib import error, utils

class audiovideo_FFMPEG(test.test):
    version = 1

    def setup(self):
        """ copy test asset to bindir. """
        if not os.path.exists(self.srcdir):
            os.mkdir(self.srcdir)
        # sysroot = os.environ["SYSROOT"]
        # testdir = os.path.join(sysroot, "usr/local/autotest-chrome")
        # testbin = os.path.join(testdir, "ffmpeg_tests")
	# TODO(jiesun): retrieve chrome test asset from build.
        # shutil.copy(testbin, self.bindir)


    def run_once(self):
        """ Run FFMPEG performance test! """
        # fetch all the test cases from file.
        testcases = os.path.join(self.bindir, "testcases")
        self.performance_results = {}
        self.min_fps_video = 100
        self.max_tpf_audio = 0

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
        if utils.get_arch() == 'i386':
            executable = os.path.join(self.bindir, "ffmpeg_tests.i686")
        else:  # TODO(jiesun): we only have ARM and i386.
            executable = os.path.join(self.bindir, "ffmpeg_tests.arm")
        file_url = testcase[0]

        # TODO(jiesun): if url is not local, grab it from internet.
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
            raise error.TestError("ffmpeg_tests: test media missing %s!"
                                  % file_url)

        command_line = ("LD_LIBRARY_PATH=/opt/google/chrome/ %s %s"
                        % (executable, file_path))
        logging.info("Running %s" % command_line)

        cpu_usage, stdout = utils.get_cpu_percentage(
                                 utils.system_output,
                                 command_line,
                                 retain_output=True)

        cpu_usage *= 100.0  # in percentage.

        # what's the fps we measures for video.
        fps_pattern = re.search(r"FPS:\s+([\d\.]+)", stdout)
        # what's the time per frame for audio.
        tpf_pattern = re.search(r"TIME PER FRAME \(MS\):\s+([\d\.]+)", stdout)
        if fps_pattern:
            fps = float(fps_pattern.group(1))
            logging.info("CPU Usage %s%%; FPS: %s" % (cpu_usage, fps))
            self.min_fps_video = min(self.min_fps_video, fps);
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


