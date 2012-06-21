# Copyright (c) 2012 The Chromium OS Authors. All rights reserved.
# Use of this source code is governed by a BSD-style license that can be
# found in the LICENSE file.

import optparse
import os
import shutil
import sys

from autotest_lib.client.common_lib import error, utils
from autotest_lib.server import test, autotest

class chromeperf_PGOPageCycler(test.test):
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


    # TODO(petermayo): crosbug.com/31826 Share this with _GsUpload in
    # //chromite.git/buildbot/prebuilt.py somewhere/somehow.
    def _gs_upload(self, local_file, remote_file, acl):
        """Upload to GS bucket.

        Args:
            local_file
            remote_file
            acl me or file used for controlling access to the uploaded file.

        Returns:
            Return the arg tuple of two if the upload failed
        """

        # https://developers.google.com/storage/docs/accesscontrol#extension
        CANNED_ACLS = ['project-private', 'private', 'public-read',
                       'public-read-write', 'authenticated-read',
                       'bucket-owner-read', 'bucket-owner-full-control']
        _GSUTIL_BIN = '/usr/bin/gsutil'

        acl_cmd = None
        if acl in CANNED_ACLS:
            cmd = [_GSUTIL_BIN, 'cp', '-a', acl, local_file, remote_file]
        else:
            # For private uploads we assume that the overlay board is set up
            # properly and a googlestore_acl.xml is present, if not this script
            # errors
            cmd = [_GSUTIL_BIN, 'cp', '-a', 'private', local_file, remote_file]
            if not os.path.exists(acl):
                raise error.TestFail('Unresolved acl %s.' % acl)
            acl_cmd = [_GSUTIL_BIN, 'setacl', acl, remote_file]

        with open(os.path.join(self.job.resultdir, 'tracing'), 'w') as ftrace:
            ftrace.write('Preamble\n')
            utils.run(cmd[0], args=cmd[1:], timeout=self._PGO_TRANSFER_TIMEOUT,
                      verbose=True, stdout_tee=ftrace, stderr_tee=ftrace)

            if acl_cmd:
                ftrace.write('\nACL setting\n')
                # Apply the passed in ACL xml file to the uploaded object.
                utils.run(acl_cmd[0], args=acl_cmd[1:],
                          timeout=self._ACL_SET_TIMEOUT,
                          verbose=True, stdout_tee=ftrace, stderr_tee=ftrace)

            ftrace.write('Postamble\n')


    def run_once(self, host=None, args=[]):
        self.parse_args(args)
        if not self.options.destination and self.job.label:
            self.options.destination = (self._DEFAULT_UPLOAD_PATTERN %
                self.job.label)

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
            'job.profilers.delete("pgo")',
        ]

        if self.options.reboot:
            self.client.reboot()

        client_at.run('\n'.join(control))

        client_results_dir = os.path.join(self.job.resultdir,
            self.server_test, self.client_test, 'profiling', 'iteration.1')
        src = os.path.join(client_results_dir, 'pgo.tar.bz2')
        if os.path.exists(src):
            if self.options.destination:
                dst = os.path.join(self.options.destination, 'pgo.tar.bz2')
                copy_text = 'from %s to %s' % (src, dst)
                if self._gs_upload(src, dst, self.options.acl) is not None:
                    raise error.TestFail('Unable to copy ' + copy_text)
