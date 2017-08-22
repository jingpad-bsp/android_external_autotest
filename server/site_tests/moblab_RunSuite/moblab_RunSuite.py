# Copyright (c) 2014 The Chromium OS Authors. All rights reserved.
# Use of this source code is governed by a BSD-style license that can be
# found in the LICENSE file.

import json
import logging
import time

from autotest_lib.client.common_lib import error
from autotest_lib.server.cros import moblab_test
from autotest_lib.server.hosts import moblab_host
from autotest_lib.utils import labellib


SUITE_TIMEOUT = 10800
WAIT_FOR_CHILD_JOB_CREATION_TIMEOUT = 5 * 60

# We can't actually import run_suite here because importing run_suite pulls
# in certain MySQLdb dependencies that fail to load in the context of a
# test.
JSON_START_TOKEN = "#JSON_START#"
JSON_END_TOKEN = "#JSON_END#"


class moblab_RunSuite(moblab_test.MoblabTest):
    """
    Moblab run suite test. Ensures that a Moblab can run a suite from start
    to finish by kicking off a suite which will have the Moblab stage an
    image, provision its DUTs and run the tests.
    """
    version = 1


    def run_once(self, host, suite_name, moblab_suite_max_retries,
                 target_build=''):
        """Runs a suite on a Moblab Host against its test DUTS.

        @param host: Moblab Host that will run the suite.
        @param suite_name: Name of the suite to run.
        @param moblab_suite_max_retries: The maximum number of test retries
                allowed within the suite launched on moblab.
        @param target_build: Optional build to be use in the run_suite
                call on moblab. This argument is passed as is to run_suite. It
                must be a sensible build target for the board of the sub-DUTs
                attached to the moblab.

        @raises AutoservRunError if the suite does not complete successfully.
        """
        # Fetch the board of the DUT's assigned to this Moblab. There should
        # only be one type.
        try:
            dut = host.afe.get_hosts()[0]
        except IndexError:
            raise error.TestFail('All hosts for this MobLab are down. Please '
                                 'request the lab admins to take a look.')

        labels = labellib.LabelsMapping(dut.labels)
        board = labels['board']

        if not target_build:
            stable_version_map = host.afe.get_stable_version_map(
                    host.afe.CROS_IMAGE_TYPE)
            target_build = stable_version_map.get_image_name(board)

        logging.info('Running suite: %s.', suite_name)
        cmd = ("%s/site_utils/run_suite.py --pool='' --board=%s --build=%s "
               "--suite_name=%s --retry=True " "--max_retries=%d"
               "--create_and_return --json_dump" %
               (moblab_host.AUTOTEST_INSTALL_DIR, board, target_build,
                suite_name, moblab_suite_max_retries))
        logging.debug('Run suite command: %s', cmd)
        try:
            result = host.run_as_moblab(cmd, timeout=SUITE_TIMEOUT)
            logging.debug('Suite Kickoff Output:\n%s', result.stdout)
        except error.AutoservRunError as e:
            if _is_run_suite_error_critical(e.result_obj.exit_status):
                raise
            else:
                logging.exception(
                        'Ignoring a non-critical exception in run_suite.')
                return

        job_id = _parse_job_id(result.stdout)
        if job_id is None:
            raise error.TestFail('Could not start a suite job, or could not '
                                 'parse a job_id from the run_suite.py output.')

        found_child = self._wait_for_child_job_creation(
                job_id, timeout=WAIT_FOR_CHILD_JOB_CREATION_TIMEOUT)

        if not found_child:
            # See crbug.com/718618. If the scheduler crashes, no child job will
            # be created.
            raise error.TestFail(
                    'Failed to start a child job within the time limit '
                    '(%s minutes); probably this is due to a bug in the '
                    'scheduler.'
                    % (WAIT_FOR_CHILD_JOB_CREATION_TIMEOUT / 60.0))

        try:
            result = host.run_as_moblab(
                '%s/site_utils/run_suite.py --board=%s --build=%s '
                '--suite_name=%s --mock_job_id %s' %
                (moblab_host.AUTOTEST_INSTALL_DIR, board, target_build,
                 suite_name, job_id),
                timeout=SUITE_TIMEOUT)
            logging.debug('Suite Result Output:\n%s', result.stdout)
        except error.AutoservRunError as e:
            if _is_run_suite_error_critical(e.result_obj.exit_status):
                raise
            else:
                logging.exception(
                        'Ignoring a non-critical exception in run_suite.')

    def _wait_for_child_job_creation(self, job_id, timeout,
                                     poll_interval_seconds=10):
        """Waits |timeout| seconds for job |job_id| to have a child job.

        @param job_id: The job id of the suite job.
        @param timeout: The maximum amount of time in seconds to poll for.
        @param poll_interval_seconds: The number of seconds to sleep in between
            each query RPC.
        """
        start_time = time.time()
        while time.time() - start_time < timeout:
            jobs = self._afe.get_jobs(parent_job_id=job_id)
            if not jobs:
                time.sleep(poll_interval_seconds)
            else:
                return True
        return False


def _parse_job_id(run_suite_output):
    """Parses the job id from the output of a run suite invocation."""
    try:
        _, json_start = run_suite_output.split(JSON_START_TOKEN)
        json_body = json_start.split(JSON_END_TOKEN)
        return json.loads(json_body).get('job_id')
    except ValueError:
        return None


def _is_run_suite_error_critical(return_code):
    # We can't actually import run_suite here because importing run_suite pulls
    # in certain MySQLdb dependencies that fail to load in the context of a
    # test.
    # OTOH, these return codes are unlikely to change because external users /
    # builders depend on them.
    return return_code not in (
            0,  # run_suite.RETURN_CODES.OK
            2,  # run_suite.RETURN_CODES.WARNING
    )
