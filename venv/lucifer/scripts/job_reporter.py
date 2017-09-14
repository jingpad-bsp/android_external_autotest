# Copyright 2017 The Chromium Authors. All rights reserved.
# Use of this source code is governed by a BSD-style license that can be
# found in the LICENSE file.

from __future__ import absolute_import
from __future__ import division
from __future__ import print_function

import argparse
import logging
import sys

from lucifer import eventlib
from lucifer import loglib

logger = logging.getLogger(__name__)

# TODO(crbug.com/748234): This is for moblab.  Prod may require
# different path.
_JOB_SHEPHERD_PROGRAM = '/usr/lib/job_shepherd'


def main(args):
    """Main function

    @param args: list of command line args
    """
    parser = argparse.ArgumentParser(prog='job_reporter')
    loglib.add_logging_options(parser)
    args = parser.parse_args(args)
    loglib.configure_logging_with_args(parser, args)
    return _run_shepherd(_handle_event)


def _run_shepherd(event_handler):
    """Run job_shepherd.

    Events issues by the job_shepherd will be handled by event_handler.

    @param event_handler: callable that takes an Event.
    """
    return eventlib.run_event_command(
            event_handler=event_handler,
            args=[_JOB_SHEPHERD_PROGRAM])


def _handle_event(event):
    logger.debug('Received event %r', event.name)


if __name__ == '__main__':
    sys.exit(main(sys.argv[1:]))
