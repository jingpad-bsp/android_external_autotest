# Copyright 2017 The Chromium Authors. All rights reserved.
# Use of this source code is governed by a BSD-style license that can be
# found in the LICENSE file.

"""Grab fcntl lock on file.

This is used for testing leasing.
"""

from __future__ import absolute_import
from __future__ import division
from __future__ import print_function

import fcntl
import logging
import os
import sys
import time

from lucifer import loglib

logger = logging.getLogger(__name__)


def main(_args):
    """Main function

    @param args: list of command line args
    """
    loglib.configure_logging(name='fcntl_lock')
    fd = os.open(sys.argv[1], os.O_WRONLY)
    logger.debug('Opened %s', sys.argv[1])
    fcntl.lockf(fd, fcntl.LOCK_EX)
    logger.debug('Grabbed lock')
    print('done')
    while True:
        time.sleep(10)


if __name__ == '__main__':
    sys.exit(main(sys.argv[1:]))
