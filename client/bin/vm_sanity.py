#!/usr/bin/python
#
# Copyright 2016 The Chromium OS Authors. All rights reserved.
# Use of this source code is governed by a BSD-style license that can be
# found in the LICENSE file.

'''A simple sanity test for Chrome.

This script logs in, ensures that the cryptohome is mounted,
and checks that the browser is functional.
'''

import logging
import sys

# This sets up import paths for autotest.
import common
from autotest_lib.client.common_lib.cros import chrome
from autotest_lib.client.common_lib.error import TestFail
from autotest_lib.client.cros import cryptohome


def main(args):
    '''The main function.'''
    if args:
      print "No args for vm_sanity.py"
      return 64  # EX_USAGE

    logging.info('Starting chrome and logging in.')
    with chrome.Chrome() as cr:
        # Check that the cryptohome is mounted.
        # is_vault_mounted throws an exception if it fails.
        logging.info('Checking mounted cryptohome.')
        cryptohome.is_vault_mounted(user=cr.username, allow_fail=False)
        # Evaluate some javascript.
        logging.info('Evaluating JavaScript.')
        if cr.browser.tabs[0].EvaluateJavaScript('2+2') != 4:
          raise TestFail('EvaluateJavaScript failed')
    logging.info('Test succeeded.')

if __name__ == '__main__':
    sys.exit(main(sys.argv[1:]))
