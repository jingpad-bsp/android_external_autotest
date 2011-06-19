# Copyright (c) 2010 The Chromium OS Authors. All rights reserved.
# Use of this source code is governed by a BSD-style license that can be
# found in the LICENSE file.

import glob
import logging
import os
import pprint
import re
from autotest_lib.client.bin import factory, test, utils
from autotest_lib.client.common_lib import error
from autotest_lib.client.cros import gooftools


class hardware_Components(test.test):
    version = 3

    def run_once(self, approved_dbs='approved_components'):
        # Checks if current system matches a hardware configuration in the
        # databases.
        # Currently the files are expected to be inside same folder with
        # hardware_Components test.

        approved_dbs = os.path.join(self.bindir, approved_dbs)
        sample_approved_dbs = os.path.join(self.bindir,
                                           'approved_components.default')
        if (not glob.glob(approved_dbs)) and glob.glob(sample_approved_dbs):
            # Fallback to the default (sample) version
            approved_dbs = sample_approved_dbs
            factory.log('Using default (sample) approved component list: %s'
                        % sample_approved_dbs)

        # approved_dbs supports shell-like filename expansion.
        existing_dbs = glob.glob(approved_dbs)
        if not existing_dbs:
            raise error.TestError('Unable to find approved db: %s' %
                                  approved_dbs)

        command = ('gooftool --verify_hwid --db_path "%s" --verbose' %
                   approved_dbs)
        pattern = 'Verified: '
        # The output format is "Verified: PATH (HWID)", not a pure path.

        (stdout, stderr, result) = gooftools.run(command, ignore_status=True)

        # Decode successfully matched results
        hwids = [hwid.lstrip(pattern)
                 for hwid in stdout.splitlines()
                 if hwid.startswith(pattern)]

        # Decode unmatched results
        if stderr.find('Unmatched ') < 0:
            unmatched = ''
        else:
            start = stderr.find('Unmatched ')
            end = stderr.rfind('Current System:')
            if end >= 0:
                unmatched = stderr[start:end]
            else:
                unmatched = stderr[start:]
            unmatched = '\n'.join([line for line in unmatched.splitlines()
                                   # 'gft_hwcome'/'probe' are debug message.
                                   if not (line.startswith('gft_hwcomp:') or
                                           line.startswith('probe:') or
                                           (not line))])
        # Report the results
        if len(hwids) < 1:
            raise error.TestFail('\n'.join(('No HWID matched.', unmatched)))
        if len(hwids) > 1:
            raise error.TestError('Multiple HWIDs match current system: ' +
                                  ','.join(hwids))
        if result != 0:
            raise error.TestFail('HWID matched (%s) with unknown error: %s'
                                 % hwids[0], result)

        factory.log('Exact Matched: HWID=%s' % hwids[0])
