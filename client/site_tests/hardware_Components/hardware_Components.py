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

        last_probed_hwid = None
        if not do_probe:
            # verify, or trust previous probed.
            try:
                last_probed_hwid = factory.get_shared_data('last_probed_hwid')
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
            probed_hwids = gooftools.run(
                    'gooftool --probe --db_path "%s" --verbose' % approved_dbs)
            pattern = 'Probed: '
            factory.log('probe result: ' + probed_hwids)
            probed_hwids = [hwid.lstrip(pattern)
                            for hwid in probed_hwids.splitlines()
                            if hwid.startswith(pattern)]
            if len(probed_hwids) < 1:
                raise error.TestFail('No HWID matched.')
            if len(probed_hwids) > 1:
                raise error.TestError('Multiple HWIDs match current system: ' +
                                      ','.join(probed_hwids))
            factory.log('Set last_probed_hwid = %s' % probed_hwids[0])
            try:
                factory.set_shared_data('last_probed_hwid', probed_hwids[0])
            except Exception, e:
                # hardware_Components may run without factory environment
                factory.log('Failed setting shared data, ignored: %s' %
                            repr(e))
        else:
            verified_hwids = gooftools.run(
                    'gooftool --verify_hwid --db_path "%s" --verbose' %
                    approved_dbs)
            pattern = 'Verified: '
            # The 'verified hwid' is in format "PATH (HWID)", so we can only use
            # it for logging instead of using it directly like in probing.
            verified_hwids = [hwid.lstrip(pattern)
                              for hwid in verified_hwids.splitlines()
                              if hwid.startswith(pattern)]
            if len(probed_hwids) < 1:
                raise error.TestFail('No HWID matched.')
            if len(verified_hwids) > 1:
                raise error.TestError('Multiple HWIDs match current system: ' +
                                      ','.join(verified_hwids))
            factory.log('Verified: HWID=%s' % verified_hwids[0])
