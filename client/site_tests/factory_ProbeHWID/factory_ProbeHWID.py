# Copyright (c) 2011 The Chromium OS Authors. All rights reserved.
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


class factory_ProbeHWID(test.test):
    version = 3

    def run_once(self):
        # Find out the matching HWID and write into shared data
        # LAST_PROBED_HWID_NAME, and then let factory_WriteGBB to
        # update system. factory_Finalize will verify if that's set correctly.

        command = 'gooftool --probe --verbose'
        pattern = 'Probed: '

        (stdout, stderr, result) = gooftools.run(command, ignore_status=True)

        # Decode successfully matched results
        hwids = [hwid.lstrip(pattern)
                 for hwid in stdout.splitlines()
                 if hwid.startswith(pattern)]

        # Decode unmatched results.
        # Sample output:
        #  Unmatched for /usr/local/share/chromeos-hwid/components_BLAHBLAH:
        #  { 'part_id_3g': ['Actual: XXX', 'Expected: YYY']}
        #  Current System:
        #  { 'part_id_xxx': ['yyy'] },
        str_unmatched = 'Unmatched '
        str_current = 'Current System:'

        start = stderr.find(str_unmatched)
        if start < 0:
            unmatched = ''
        else:
            end = stderr.rfind(str_current)
            if end >= 0:
                unmatched = stderr[start:end]
            else:
                unmatched = stderr[start:]
            unmatched = '\n'.join([line for line in unmatched.splitlines()
                                   # 'gft_hwcomp' or 'probe' are debug message.
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
        factory.log('Set factory state shared data %s = %s' %
                    (factory.LAST_PROBED_HWID_NAME, hwids[0]))
        try:
            factory.set_shared_data(factory.LAST_PROBED_HWID_NAME,
                                    hwids[0])
        except Exception, e:
            # factory_ProbeHWID may run without factory environment
            factory.log('Failed setting shared data, ignored: %s' %
                        repr(e))
        factory.log('Exact Matched: HWID=%s' % hwids[0])
