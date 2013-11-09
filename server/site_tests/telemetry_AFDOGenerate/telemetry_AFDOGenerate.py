# Copyright (c) 2013 The Chromium OS Authors. All rights reserved.
# Use of this source code is governed by a BSD-style license that can be
# found in the LICENSE file.

"""
Test to generate the AFDO profile for a set of ChromeOS benchmarks.

This will run a pre-determined set of benchmarks on the DUT under
the monitoring of the linux "perf" tool. The resulting perf.data
file will then be copied to Google Storage (GS) where it can be
used by the AFDO optimized build.

Example invocation:
/usr/bin/test_that --debug --board=lumpy <DUT IP>
  --args="ignore_failures=True local=True gs_test_location=True"
  telemetry_PGOGenerate
"""

import bz2
import logging
import os

from autotest_lib.client.common_lib import error, utils
from autotest_lib.server import test
from autotest_lib.server import utils
from autotest_lib.server.cros import telemetry_runner

# List of benchmarks to run to capture profile information. This is
# based on the "perf_v2" list and other telemetry benchmarks. Goal is
# to have a short list that is as representative as possible and takes
# a short time to execute. At this point the list of benchmarks is in
# flux.  Some of the benchmarks here may not be good for our purposes
# (take too long or are too flaky).
TELEMETRY_AFDO_BENCHMARKS = [
        'dromaeo.domcoreattr',
        'dromaeo.domcoremodify',
        'dromaeo.domcorequery',
        'dromaeo.domcoretraverse',
        'kraken',
        'memory.top_25',
        'octane',
        'robohornet_pro',
        'smoothness.top_25',
        'sunspider',
        'jsgamebench',
        'page_cycler.indexed_db.basic_insert',
        'page_cycler.bloat',
        'page_cycler.dhtml',
        'page_cycler.intl_ar_fa_he',
        'page_cycler.intl_es_fr_pt-BR',
        'page_cycler.intl_hi_ru',
        'page_cycler.intl_ja_zh',
        'page_cycler.intl_ko_th_vi',
        'page_cycler.morejs',
        'page_cycler.moz',
        'page_cycler.netsim.top_10',
        'page_cycler.typical_25' ]


# List of boards where this test can be run.
VALID_BOARDS = ['lumpy', 'parrot']

class telemetry_AFDOGenerate(test.test):
    """
    Run one or more telemetry benchmarks under the "perf" monitoring
    tool, generate a "perf.data" file and upload to GS for comsumption
    by the AFDO optimized build.
    """
    version = 1


    def run_once(self, host, args, stdout='', stderr=''):
        """Run a single telemetry test.

        @param host: Host machine where test is run
        @param args: A dictionary of the arguments that were passed
                to this test.
        @returns A TelemetryResult instance with the results of this
                execution.
        """
        self._host = host
        host_board = host.get_board().split(':')[1]
        if not host_board in VALID_BOARDS:
            raise error.TestFail(
                    'This test cannot be run on board %s' % host_board)

        self._parse_args(args)
        self._telemetry_runner = telemetry_runner.TelemetryRunner(
                host, self._local)

        for benchmark in TELEMETRY_AFDO_BENCHMARKS:
            self._run_test(benchmark)


    def after_run_once(self):
        """After the profile information has been collected, compress it
        and upload it to GS
        """
        PERF_FILE = 'perf.data'
        COMP_PERF_FILE = 'chromeos-chrome-%s-%s.perf.data'
        perf_data = os.path.join(self.profdir, PERF_FILE)
        comp_data = os.path.join(self.profdir, COMP_PERF_FILE % (
                self._arch, self._version))
        compressed = self._compress_file(perf_data, comp_data)
        self._gs_upload(compressed, os.path.basename(compressed))

        # Also create copy of this file using "LATEST" as version so
        # it can be found in case the builder is looking for a version
        # number that does not match. It is ok to use a slighly old
        # version of the this file for the optimized build
        latest_data =  COMP_PERF_FILE % (self._arch, 'LATEST')
        latest_compressed = self._get_compressed_name(latest_data)
        self._gs_upload(compressed, latest_compressed)


    def _parse_args(self, args):
        """Parses input arguments to this autotest.

        @param args: Options->values dictionary.
        @raises error.TestFail if a bad option is passed.
        """

        # Set default values for the options.
        # Architecture for which we are collecting afdo data.
        self._arch = 'amd64'
        # Use an alternate GS location where everyone can write.
        # Set default depending on whether this is executing in
        # the lab environment or not
        self._gs_test_location = not utils.host_is_in_lab_zone(
                self._host.hostname)
        # Ignore individual test failures.
        # TODO(llozano): Change default to False when tests are more stable.
        self._ignore_failures = True
        # Use local copy of telemetry instead of using the dev server copy.
        self._local = False
        # Chrome version to which the AFDO data corresponds.
        self._version = '9999'

        for option_name, value in args.iteritems():
            if option_name == 'arch':
                self._arch = value
            elif option_name == 'gs_test_location':
                self._gs_test_location = (value == 'True')
            elif option_name == 'ignore_failures':
                self._ignore_failures = (value == 'True')
            elif option_name == 'local':
                self._local = (value == 'True')
            elif option_name == 'version':
                self._version = value
            else:
                raise error.TestFail('Unknown option passed: %s' % option_name)


    def _run_test(self, benchmark):
        """Run the benchmark using Telemetry.

        @param Name of the benchmark to run.
        @raises if failures are not being ignored raises error.TestFail if
                execution of test failed. Also re-raise any exceptions thrown
                by run_telemetry benchmark.
        """
        try:
            result = self._telemetry_runner.run_telemetry_benchmark(benchmark)
        except error.TestBaseException as e:
            if not self._ignore_failures:
                raise
            else:
                logging.info('Ignoring exception from benchmark %s', benchmark)
                return

        # We dont generate any keyvals for this run. This is not
        # an official run of the benchmark. We are just running it to get
        # a profile from it.

        if result.status is telemetry_runner.SUCCESS_STATUS:
            logging.info('Benchmark %s succeeded', benchmark)
        else:
            if not self._ignore_failures:
                raise error.TestFail ('An error occurred while executing'
                                      ' benchmark: %s' % benchmark)
            else:
                logging.info('Ignoring failure from benchmark %s', benchmark)


    @staticmethod
    def _get_compressed_name(name):
        """Given a file name, return bz2 compressed name.
        @param name: Name of uncompressed file.
        @returns name of compressed file.
        """
        return name + '.bz2'

    @staticmethod
    def _compress_file(unc_file, com_file):
        """Compresses specified file with bz2.

        @param unc_file: name of file to compress.
        @param com_file: prefix name of compressed file.
        @raises error.TestFail if compression failed
        @returns Name of compressed file.
        """
        dest = ''
        with open(unc_file, 'r') as inp:
            dest = telemetry_AFDOGenerate._get_compressed_name(com_file)
            with bz2.BZ2File(dest, 'w') as out:
                for data in inp:
                    out.write(data)
        if not dest or not os.path.isfile(dest):
            raise error.TestFail('Could not compress %s' % unc_file)
        return dest


    def _gs_upload(self, local_file, remote_basename):
        """Uploads file to google storage specific location.

        @param local_file: name of file to upload.
        @param remote_basename: basename of remote file.
        @raises error.TestFail if upload failed.
        @returns nothing.
        """
        GS_DEST = 'gs://chromeos-prebuilt/afdo-job/canonicals/%s'
        GS_TEST_DEST = 'gs://chromeos-throw-away-bucket/afdo-job/canonicals/%s'
        GS_ACL = 'project-private'

        gs_dest = GS_TEST_DEST if self._gs_test_location else GS_DEST

        if not utils.gs_upload(local_file,
                               gs_dest % remote_basename,
                               GS_ACL, result_dir=self.resultsdir):
            raise error.TestFail('Unable to gs upload %s to %s as %s' %
                                 (local_file, gs_dest, remote_basename))
