# Copyright (c) 2010 The Chromium OS Authors. All rights reserved.
# Use of this source code is governed by a BSD-style license that can be
# found in the LICENSE file.

import glob, logging, os, re, stat, time, urllib

from autotest_lib.client.bin import test
from autotest_lib.client.common_lib import error, utils

class audiovideo_FFMPEG(test.test):
    version = 1

    def run_once(self):
        """ Run FFMPEG performance test! """
        # fetch all the test cases from file.
        testcases = os.path.join(self.bindir, "testcases")
        self.performance_results = {}
        for line in open(testcases, "rt"):
            # skip comment line and blank line
            line = line.rstrip()
            if len(line) == 0: continue
            if line[0] == "#": continue
            # run each test cases
            testcase = line.split()
            self.run_testcase(testcase)
        self.write_perf_keyval(self.performance_results)


    def run_testcase(self, testcase):
        executable = os.path.join(self.bindir, "ffmpeg_tests.i686")
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

        # what's the fps we measures.
        fps_pattern = re.search(r"FPS:\s+([\d\.]+)", stdout)
        if fps_pattern is None:
            raise error.TestFail("ffmpeg_tests failed to exit normally!")
        fps = float(fps_pattern.group(1))
        cpu_usage *= 100.0  # in percentage.
        logging.info("Cpu Usage %s%%; FPS: %s" % (cpu_usage, fps))

        # record the performance data for future analysis.
        self.performance_results['fps_' + file_name] = fps
        self.performance_results['cpuusage_' + file_name] = cpu_usage

        # TODO(jiesun/fbarchard): what else need to be checked?

