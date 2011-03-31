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

    def run_once(self, approved_dbs='approved_components', do_probe=True):
        # In probe mode, we have to find out the matching HWID, write that into
        # shared data LAST_PROBED_HWID_NAME, and then let factory_WriteGBB to
        # update system. factory_Finalize will verify if that's set correctly.
        #
        # In verify mode, we simply check if current system matches a hardware
        # configuration in the databases.

        last_probed_hwid = None
        if not do_probe:
            # Verify, or trust previous probed HWID.
            try:
                last_probed_hwid = factory.get_shared_data(
                        factory.LAST_PROBED_HWID_NAME)
            except Exception, e:
                # hardware_Components may run without factory environment
                factory.log('Failed getting shared data, ignored: %s' % repr(e))

        # If a hwid was probed, trust it. Otherwise, find best match.
        if last_probed_hwid:
            approved_dbs = last_probed_hwid
        else:
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

        if do_probe:
            command = 'gooftool --probe --db_path "%s" --verbose' % approved_dbs
            pattern = 'Probed: '
            # The output format is "Probed: PATH"
        else:
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

        # Set the factory state sharead data for factory_WriteGBB
        if do_probe:
            factory.log('Set factory state shared data %s = %s' %
                        (factory.LAST_PROBED_HWID_NAME, hwids[0]))
            try:
                factory.set_shared_data(factory.LAST_PROBED_HWID_NAME,
                                        hwids[0])
            except Exception, e:
                # hardware_Components may run without factory environment
                factory.log('Failed setting shared data, ignored: %s' %
                            repr(e))
        factory.log('Exact Matched: HWID=%s' % hwids[0])
