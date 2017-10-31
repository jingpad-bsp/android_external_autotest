# Copyright (c) 2014 The Chromium OS Authors. All rights reserved.
# Use of this source code is governed by a BSD-style license that can be
# found in the LICENSE file.

import logging

from autotest_lib.client.common_lib import error
from autotest_lib.server.cros import moblab_test
from autotest_lib.server.hosts import moblab_host
from autotest_lib.utils import labellib


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
               "--suite_name=%s --retry=True " "--max_retries=%d" %
               (moblab_host.AUTOTEST_INSTALL_DIR, board, target_build,
                suite_name, moblab_suite_max_retries))
        logging.debug('Run suite command: %s', cmd)
        try:
            result = host.run_as_moblab(cmd, timeout=10800)
        except error.AutoservRunError as e:
            if _is_run_suite_error_critical(e.result_obj.exit_status):
                raise
        else:
            logging.debug('Suite Run Output:\n%s', result.stdout)


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
