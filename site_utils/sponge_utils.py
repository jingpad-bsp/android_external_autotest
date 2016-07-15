# Copyright 2016 The Chromium Authors. All rights reserved.
# Use of this source code is governed by a BSD-style license that can be
# found in the LICENSE file.

"""This module contains utilities for test to report result to Sponge.
"""

import logging
import socket
import time

import common

try:
    import sponge
except ImportError:
    logging.debug('Module failed to be imported: sponge')
    sponge = None

from autotest_lib.client.common_lib import decorators
from autotest_lib.client.common_lib import global_config
from autotest_lib.site_utils import job_directories
from autotest_lib.tko import models
from autotest_lib.tko import utils as tko_utils


CONFIG=global_config.global_config

RETRIEVE_LOGS_CGI = CONFIG.get_config_value(
        'BUG_REPORTING', 'retrieve_logs_cgi', default='')
RESULTS_URL_FMT = RETRIEVE_LOGS_CGI + 'results/%s-%s/%s'
USE_PROD_SERVER = CONFIG.get_config_value(
        'SERVER', 'use_prod_sponge_server', default=False, type=bool)

@decorators.test_module_available(sponge)
def upload_results_in_test(test, test_pass=True, acts_summary=None):
    """Upload test results to Sponge.

    @param test: A test object.
    @param test_pass: True if test passed, False otherwise. Default is set to
            True. When test results are reported inside test, the test is
            considered to success, or exception like TestFail would have been
            raised if the test has failed.
    @param acts_summary: Path to the json file of ACTS test summary.
    """
    try:
        # job keyval file has the information about the test job except
        # `job_finished`, which is written after the test is actually finished.
        # Therefore, the `end_time` for a Sponge invocation is set to current
        # time.
        job_keyvals = models.test.parse_job_keyval(test.resultsdir)
        status = 'GOOD' if test_pass else 'FAIL'
        job_id = job_directories.get_job_id_or_task_id(test.resultsdir)
        results_dir = tko_utils.find_toplevel_job_dir(test.resultsdir)
        dut = test.job.machines[0] if len(test.job.machines) > 0 else ''
        results_url = RESULTS_URL_FMT % (job_id, test.job.user, dut)

        invocation_url = sponge.upload_utils.Upload(
                job_id=job_id,
                test_name=test.tagged_testname,
                dut=','.join(test.job.machines),
                drone=job_keyvals.get('drone', socket.gethostname()),
                status=status,
                start_time=job_keyvals['job_started'],
                end_time=time.time(),
                results_dir=results_dir,
                results_url=results_url,
                acts_summary=acts_summary,
                use_prod_server=USE_PROD_SERVER)
        logging.debug('Test result is uploaded to Sponge: %s', invocation_url)
        return invocation_url
    except Exception as e:
        logging.exception('Failed to upload to Sponge: %s', e)
