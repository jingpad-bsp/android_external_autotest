# Copyright (c) 2009 The Chromium OS Authors. All rights reserved.
# Use of this source code is governed by a BSD-style license that can be
# found in the LICENSE file.

import logging
import os
import shutil
from autotest_lib.server import test, autotest


class platform_BootPerfServer(test.test):
    version = 1


    def run_once(self, host=None):
        self.client = host
        self.client_test = 'platform_BootPerf'

        # Reboot the client
        logging.info('BootPerfServer: reboot %s' % self.client.hostname)
        self.client.reboot()

        # Collect the performance metrics by running a client side test
        logging.info('BootPerfServer: start client test')
        client_at = autotest.Autotest(self.client)
        client_at.run_test(self.client_test, last_boot_was_reboot=True)

        # In the client results directory are a 'keyval' file, and
        # various raw bootstat data files.  First promote the client
        # test 'keyval' as our own.
        logging.info('BootPerfServer: gather client results')
        client_results_dir = os.path.join(self.outputdir,
            self.client_test, "results")
        src = os.path.join(client_results_dir, "keyval")
        dst = os.path.join(self.resultsdir, "keyval")
        if os.path.exists(src):
            client_results = open(src, "r")
            server_results = open(dst, "a")
            shutil.copyfileobj(client_results, server_results)
            server_results.close()
            client_results.close()
        else:
            logging.warn('Unable to locate %s' % src)

        # Everything that isn't the client 'keyval' file is raw data
        # from the client test:  copy it to a per-iteration
        # subdirectory.
        if self.iteration is not None:
            rawdata_dir = "rawdata.%03d" % self.iteration
        else:
            rawdata_dir = "rawdata"
        rawdata_dir = os.path.join(self.resultsdir, rawdata_dir)
        os.mkdir(rawdata_dir)
        for fn in os.listdir(client_results_dir):
            if fn == "keyval":
                continue
            shutil.copy(os.path.join(client_results_dir, fn), rawdata_dir)
