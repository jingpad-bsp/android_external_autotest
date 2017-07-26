# Copyright 2017 The Chromium OS Authors. All rights reserved.
# Use of this source code is governed by a BSD-style license that can be
# found in the LICENSE file.

"""Utility to deploy and run result utils on a DUT.

This module is the one imported by other Autotest code and run result
throttling. Other modules in result_tools are designed to be copied to DUT and
executed with command line. That's why other modules (except view.py and
unittests) don't import the common module.
"""

import logging
import os

import common
from autotest_lib.client.common_lib import error
from autotest_lib.client.common_lib import global_config
from autotest_lib.client.common_lib import utils as client_utils

try:
    from chromite.lib import metrics
except ImportError:
    metrics = client_utils.metrics_mock

CONFIG = global_config.global_config
ENABLE_RESULT_THROTTLING = CONFIG.get_config_value(
        'AUTOSERV', 'enable_result_throttling', type=bool, default=False)

THROTTLE_OPTION_FMT = '-m %s'
BUILD_DIR_SUMMARY_CMD = '%s/result_tools/utils.py -p %s %s'
BUILD_DIR_SUMMARY_TIMEOUT = 120

# Default autotest directory on host
DEFAULT_AUTOTEST_DIR = '/usr/local/autotest'

def run_on_client(host, client_results_dir):
    """Run result utils on the given host.

    @param host: Host to run the result utils.
    @param client_results_dir: Path to the results directory on the client.
    @return: True: If the command runs on client without error.
             False: If the command failed with error in result throttling.
    """
    success = False
    with metrics.SecondsTimer(
            'chromeos/autotest/job/dir_summary_collection_duration',
            fields={'dut_host_name': host.hostname}):
        try:
            autodir = host.autodir or DEFAULT_AUTOTEST_DIR
            logging.debug('Deploy result utilities to %s', host.hostname)
            host.send_file(os.path.dirname(__file__), autodir)
            logging.debug('Getting directory summary for %s.',
                          client_results_dir)
            throttle_option = ''
            if ENABLE_RESULT_THROTTLING:
                throttle_option = (THROTTLE_OPTION_FMT %
                                   host.job.max_result_size_KB)
            cmd = (BUILD_DIR_SUMMARY_CMD %
                   (autodir, client_results_dir + '/', throttle_option))
            host.run(cmd, ignore_status=False,
                     timeout=BUILD_DIR_SUMMARY_TIMEOUT)
            success = True
        except error.AutoservRunError:
            logging.exception(
                    'Failed to create directory summary for %s.',
                    client_results_dir)

    return success
