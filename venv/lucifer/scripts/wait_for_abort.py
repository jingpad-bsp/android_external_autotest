# Copyright 2017 The Chromium Authors. All rights reserved.
# Use of this source code is governed by a BSD-style license that can be
# found in the LICENSE file.

"""Wait for an abort command.

This is used for testing run_event_command().

See eventlib for information about event commands.
"""

from __future__ import absolute_import
from __future__ import division
from __future__ import print_function

import sys

from lucifer import loglib


def main(_args):
    """Main function

    @param args: list of command line args
    """
    loglib.configure_logging(name='wait_for_abort')
    while True:
        line = sys.stdin.readline()
        if line == 'abort\n':
            sys.exit(0)


if __name__ == '__main__':
    sys.exit(main(sys.argv[1:]))
