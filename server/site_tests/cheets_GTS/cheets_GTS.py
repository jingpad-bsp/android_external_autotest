# Copyright 2016 The Chromium OS Authors. All rights reserved.
# Use of this source code is governed by a BSD-style license that can be
# found in the LICENSE file.

# repohooks/pre-upload.py currently does not run pylint. But for developers who
# want to check their code manually we disable several harmless pylint warnings
# which just distract from more serious remaining issues.
#
# The instance variable _android_gts is not defined in __init__().
# pylint: disable=attribute-defined-outside-init
#
# Many short variable names don't follow the naming convention.
# pylint: disable=invalid-name

import logging
import os

from autotest_lib.server import utils
from autotest_lib.server.cros import tradefed_test

_PARTNER_GTS_LOCATION = 'gs://chromeos-partner-gts/gts-5.0_r2-4389763.zip'


class cheets_GTS(tradefed_test.TradefedTest):
    """Sets up tradefed to run GTS tests."""
    version = 1


    def setup(self, uri=None):
        """Set up GTS bundle from Google Storage.

        @param uri: The location to pull the GTS bundle from.
        """
        if uri:
            self._android_gts = self._install_bundle(uri)
        else:
            self._android_gts = self._install_bundle(_PARTNER_GTS_LOCATION)

        self._repository = os.path.join(self._android_gts, 'android-gts')
        self.waivers = self._get_expected_failures('expectations')
        self.notest_modules = self._get_expected_failures('notest_modules')


    def _tradefed_run_command(self, target_module=None, plan=None,
                              session_id=None):
        """Builds the GTS command line.

        @param target_module: the module to be run.
        @param plan: the plan to be run.
        @param session_id: tradfed session id to continue.
        """
        args = ['run', 'commandAndExit', 'gts']
        if target_module is not None:
            args += ['--module', target_module]
        elif plan is not None and session_id is not None:
            args += ['--plan', plan, '--retry', '%d' % session_id]
        return args


    def _run_tradefed(self, commands, datetime_id=None, collect_results=True):
        """Kick off GTS."""
        return self._run_gts_tradefed(commands, datetime_id, collect_results)


    def _run_gts_tradefed(self, commands, datetime_id=None,
                          collect_results=True):
        """This tests runs the GTS tradefed binary and collects results.

        @param commands: the command(s) to pass to GTS.
        @param datetime_id: For 'continue' datetime of previous run is known.
        @collect_results: skip result collection if false.
        @raise TestFail: when a test failure is detected.
        """
        gts_tradefed = os.path.join(self._repository, 'tools', 'gts-tradefed')
        logging.info('GTS-tradefed path: %s', gts_tradefed)
        # Run GTS via tradefed and obtain stdout, sterr as output.
        with tradefed_test.adb_keepalive(self._get_adb_target(),
                                         self._install_paths):
            try:
                for command in commands:
                    output = self._run(gts_tradefed,
                                       args=command,
                                       verbose=True,
                                       # Tee tradefed stdout/stderr to logs
                                       # continuously during the test run.
                                       stdout_tee=utils.TEE_TO_LOGS,
                                       stderr_tee=utils.TEE_TO_LOGS)
            except Exception:
                self.log_java_version()
                raise
            if not collect_results:
                return None
        result_destination = os.path.join(self.resultsdir, 'android-gts')

        # Gather the global log first. Datetime parsing below can abort the test
        # if tradefed startup had failed. Even then the global log is useful.
        self._collect_tradefed_global_log(output, result_destination)

        # Parse stdout to obtain datetime IDs of directories into which tradefed
        # wrote result xml files and logs.
        datetime_id = self._parse_tradefed_datetime_v2(output)
        self._collect_logs(datetime_id, result_destination)

        # Result parsing must come after all other essential operations as test
        # warnings, errors and failures can be raised here.
        return self._parse_result_v2(output, waivers=self.waivers)


    def run_once(self, target_package=None, gts_tradefed_args=None):
        """Runs GTS with either a target module or a custom command line.

        @param target_package: the name of test module to be run.
        @param gts_tradefed_args: used to pass any specific cmd to GTS binary.
        """
        if gts_tradefed_args:
            test_command = gts_tradefed_args
            test_name = ' '.join(gts_tradefed_args)
        else:
            test_command = self._tradefed_run_command(target_package)
            test_name = 'module.%s' % target_package
        self._run_tradefed_with_retries(target_package, test_command, test_name)
