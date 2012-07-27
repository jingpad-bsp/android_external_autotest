# Copyright (c) 2011 The Chromium OS Authors. All rights res.
# Use of this source code is governed by a BSD-style license that can be
# found in the LICENSE file.

import os, re

from autotest_lib.client.bin import test, utils
from autotest_lib.client.common_lib import error

class realtimecomm_GTalkLmiCamera(test.test):
    version = 1
    camera_measurement = {}
   
    def run_once(self):
        camtool = os.path.join(self.bindir, 'camtool')
        if not os.path.exists(camtool):
            raise error.TestFail('Missing camtool binary. Make sure gtalk has '
                                 'been emerged.')

        # Run camera.
        test_cmd = "%s capture --duration 60 --histogram --norender" % camtool
        result = utils.system_output(test_cmd)

        # Get average frame per second.
        fps = re.search("with fps\: ([0-9.]+) requested", result, re.M);
        if fps and fps.group(1):
            self.camera_measurement['fps'] = float(fps.group(1))
        else:
            raise error.TestFail("No fps. Camtool output: %s" % result)

        # Get start up latency.
        latency = re.search("Camera start-up time\: (\d+)ms", result, re.M);
        if latency and latency.group(1):
            self.camera_measurement['latency'] = int(latency.group(1))
        else:
            raise error.TestFail("No latency. Camtool output: %s" % result)

        # Get jerkiness.
        jerkiness = re.search("Jerkiness: ([0-9]+\.[0-9]*)\%", result, re.M);
        if jerkiness and jerkiness.group(1):
            self.camera_measurement['jerkiness'] = float(jerkiness.group(1))
        else:
            raise error.TestFail("No jerkiness. Camtool output: %s" % result)

        # Report camera measurement.
        self.write_perf_keyval(self.camera_measurement)
