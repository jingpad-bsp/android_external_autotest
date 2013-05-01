# Copyright (c) 2012 The Chromium OS Authors. All rights reserved.
# Use of this source code is governed by a BSD-style license that can be
# found in the LICENSE file.

import optparse
import os

from autotest_lib.client.common_lib import error, utils
from autotest_lib.server import test, autotest

class chromeperf_PGOPageCycler(test.test):
    """PGO PageCycler test."""
    version = 1
    _DEFAULT_UPLOAD_PATTERN = 'gs://chromeos-prebuilt/pgo-job/%s'
    _PGO_TRANSFER_TIMEOUT = 300
    _ACL_SET_TIMEOUT = 300


    def parse_args(self, args):
        """Parses input arguments to this autotest."""
        if isinstance(args, str):
            args = args.split()

        parser = optparse.OptionParser()

        parser.add_option('--acl', type='string',
                          default='project-private',
                          help='Place to put the performance data.')
        parser.add_option('--profile-destination', type='string',
                          default=None, dest='destination',
                          help='Place to put the performance data.')
        parser.add_option('--profile-name', type='string',
                          default='chromeos-chrome-pgo.tar.bz2',
                          dest='profilename',
                          help='Name to call the performance data.')
        parser.add_option('--reboot', dest='reboot', action='store_true',
                          default=True,
                          help='Reboot the client before the test')
        parser.add_option('--no-reboot', dest='reboot', action='store_false',
                          help='Do not reboot the client before the test')

        # Preprocess the args to remove quotes before/after each one if they
        # exist.  This is necessary because arguments passed via
        # run_remote_tests.sh may be individually quoted, and those quotes must
        # be stripped before they are parsed.
        (options, extras) = parser.parse_args(map(
             lambda arg: arg.strip('\'\"'), args))
        self.options = options
        self.extra_args = extras


    def run_once(self, host=None, args=[]):
        self.parse_args(args)

        self.client = host
        self.client_test = 'desktopui_PyAutoPerfTests'
        self.server_test = 'chromeperf_PGOPageCycler'

        client_at = autotest.Autotest(self.client)

        # Generate a control file that adds the client test with the
        # profiler to generate and store the tar file on the client.
        control = [
            # run_remote_tests.sh does this, not sure if necessary here.
            'job.default_profile_only = True',
            'job.profilers.add("pgo")',
            'job.run_test("%s", host="%s", disable_sysinfo=True, '
                'args=["--pgo", "--suite=PGO", "--iterations=1"])'
                % (self.client_test, host),
            # Causes the tar file to get written
            'job.profilers.delete("pgo")'
        ]

        if self.options.reboot:
            self.client.reboot()

        client_at.run('\n'.join(control))

        client_results_dir = os.path.join(self.job.resultdir,
            self.server_test, self.client_test, 'profiling', 'iteration.1')
        src = os.path.join(client_results_dir, 'pgo.tar.bz2')
        if os.path.exists(src):
            if not self.options.destination:
                verfile = os.path.join(client_results_dir, 'profiledestination')
                if os.path.exists(verfile):
                    with open(verfile, 'r') as f:
                        self.options.destination = f.read().strip()
            if self.options.destination:
                if not utils.gs_upload(src, self.options.destination,
                        self.options.acl, result_dir=self.job.resultdir):
                    raise error.TestFail('Unable to copy from %s to %s' %
                                         (src, self.options.destination))
            else:
                raise error.TestError('No destination for PGO specified.')
        else:
            raise error.TestError('Could not find data file: %s' % src)
