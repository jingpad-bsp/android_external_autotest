# Copyright (c) 2012 The Chromium OS Authors. All rights reserved.
# Use of this source code is governed by a BSD-style license that can be
# found in the LICENSE file.

import logging
import os
import subprocess

from autotest_lib.client.common_lib import utils
from autotest_lib.server import test, autotest


class desktopui_PyAutoPerf(test.test):
    version = 1
    _GS_PATH_FORMAT = 'gs://chromeos-image-archive/%s/%s/pyauto_perf.results'


    def run_once(self, host=None, args=[]):
        self.client = host
        self.client_test = 'desktopui_PyAutoPerfTests'
        self.server_test = 'desktopui_PyAutoPerf'
        client_at = autotest.Autotest(self.client)
        client_at.run_test(self.client_test, args=str(args))
        if not self.job.label:
            logging.debug('Job has no label, therefore not uploading perf'
                          ' results to google storage.')
            return
        # The label is in the format of builder/build/suite/test
        result_file = os.path.join(self.job.resultdir, self.server_test,
                                   self.client_test, 'results', 'keyval')
        builder,build = self.job.label.split('/')[0:2]
        gs_path = self._GS_PATH_FORMAT % (builder, build)
        if not utils.gs_upload(result_file, gs_path, 'project-private'):
            raise error.TestFail('Failed to upload perf results %s to google'
                                 'storage location %s.' % (result_file,
                                                           gs_path))