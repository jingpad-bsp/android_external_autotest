# Copyright 2017 The Chromium Authors. All rights reserved.
# Use of this source code is governed by a BSD-style license that can be
# found in the LICENSE file.

"""Run an event command.

This is used for testing run_event_command() outside of Python.

See eventlib for information about event commands.
"""

from __future__ import absolute_import
from __future__ import division
from __future__ import print_function

import sys

from lucifer import eventlib
from lucifer import loglib


def main(args):
    """Main function

    @param args: list of command line args
    """
    loglib.configure_logging('run_event_command')
    return eventlib.run_event_command(
            event_handler=_handle_event,
            args=args,
            logfile=sys.stderr)


def _handle_event(event):
    print(event.name)


if __name__ == '__main__':
    sys.exit(main(sys.argv[1:]))
