# Copyright 2015 The Chromium OS Authors. All rights reserved.
# Use of this source code is governed by a BSD-style license that can be
# found in the LICENSE file.

import logging
import json
import os

import common
from autotest_lib.client.common_lib import error
from autotest_lib.client.common_lib import global_config
from autotest_lib.server import test


CONFIG_FOLDER_LOCATION = global_config.global_config.get_config_value(
        'ACTS', 'acts_config_folder', default='')


class android_ACTS(test.test):
    '''Run an Android CTS test case.'''
    version = 1
    acts_result_to_autotest = {
        'PASS': 'GOOD',
        'FAIL': 'FAIL',
        'UNKNOWN': 'WARN',
        'SKIP': 'ABORT'
    }

    def run_once(self, testbed=None, config_file=None, testbed_name=None,
                 test_case=None):
        """Run ACTS on the DUT.

        @param testbed: Testbed representing the testbed under test.
        @param config_file: Path to config file locally.
        @param testbed_name: A string that's passed to act.py's -tb option.
        @param test_case: A string that's passed to act.py's -tc option.
        """
        if not config_file:
            raise error.TestFail('A config file must be specified.')
        logging.debug('Config file: %s', config_file)
        if not os.path.exists(config_file):
            config_path = os.path.join(CONFIG_FOLDER_LOCATION, config_file)
            config_file = os.path.realpath(config_path)
            logging.debug('Config file: %s', config_file)
            if not os.path.exists(config_file):
                 raise error.TestFail('Config file: %s does not exist' %
                                      config_file)
        test_station = testbed.get_test_station()
        # Get a tempfolder on the device.
        ts_tempfolder = test_station.get_tmp_dir()
        test_station.send_file(config_file, ts_tempfolder)

        # Run the acts script.
        act_cmd = 'act.py -c %s -tb %s -tc %s' % (
                os.path.join(ts_tempfolder, os.path.basename(config_file)),
                testbed_name, test_case)
        logging.debug('Running: %s', act_cmd)
        # TODO: Change below to be test_bed.teststation_host.run
        act_result = test_station.run(act_cmd)
        logging.debug('ACTS Output:\n%s', act_result.stdout)

        # Transport all the logs to local.
        with open(config_file, 'r') as f:
            configs = json.load(f)
        log_path = os.path.join(configs['logpath'], testbed_name, 'latest')
        test_station.get_file(log_path, self.resultsdir)
        # Load summary json file.
        summary_path = os.path.join(self.resultsdir,
                                    'latest',
                                    'test_run_summary.json')
        with open(summary_path, 'r') as f:
            results = json.load(f)['Results']
        # Report results to Autotest.
        for result in results:
            verdict = self.acts_result_to_autotest[result['Result']]
            details = result['Details']
            self.job.record(verdict, None, test_case, status=(details or ''))
