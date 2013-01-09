# Copyright (c) 2012 The Chromium OS Authors. All rights reserved.
# Use of this source code is governed by a BSD-style license that can be
# found in the LICENSE file.

import logging
import os
import shutil
import subprocess

from autotest_lib.client.common_lib import error, utils
from autotest_lib.server import test, autotest


class desktopui_PyAutoPerf(test.test):
    version = 1
    _GS_PATH_FORMAT = 'gs://chromeos-image-archive/%s/%s/pyauto_perf.results'


    def run_once(self, host=None, args=[]):
        self.client = host
        self.client_test = 'desktopui_PyAutoPerfTests'
        self.server_test = 'desktopui_PyAutoPerf'
        client_at = autotest.Autotest(self.client)
        client_at.run_test(self.client_test, *args)

        # In the client results directory are a 'keyval' file, and
        # various raw pyauto perf data files.  First promote the client
        # test 'keyval' as our own.
        logging.info('PyAutoPerf: gathering client results.')
        client_results_dir = os.path.join(
            self.outputdir, self.client_test, 'results')
        src = os.path.join(client_results_dir, 'keyval')
        dst = os.path.join(self.resultsdir, 'keyval')
        if os.path.exists(src):
            client_results = open(src, 'r')
            server_results = open(dst, 'a')
            shutil.copyfileobj(client_results, server_results)
            server_results.close()
            client_results.close()
        else:
            logging.error('Unable to locate client test keyval file: %s.', src)
            return

        # Attempt to upload the perf results to google storage.
        if not self.job.label:
            logging.debug('Job has no label, therefore not uploading perf'
                          ' results to google storage.')
            return
        # The label is in the format of builder/build/suite/test
        result_file = os.path.join(self.job.resultdir, self.server_test,
                                   self.client_test, 'debug',
                                   '%s.DEBUG' % self.client_test)
        builder, build = self.job.label.split('/')[0:2]
        gs_path = self._GS_PATH_FORMAT % (builder, build)
        if not utils.gs_upload(result_file, gs_path, 'project-private'):
            raise error.TestFail('Failed to upload perf results %s to google'
                                 'storage location %s.' % (result_file,
                                                           gs_path))
