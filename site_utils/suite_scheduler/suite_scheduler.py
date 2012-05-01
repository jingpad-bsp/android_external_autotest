#!/usr/bin/python
#
# Copyright (c) 2012 The Chromium OS Authors. All rights reserved.
# Use of this source code is governed by a BSD-style license that can be
# found in the LICENSE file.

"""CrOS suite scheduler.  Will schedule suites based on configured triggers.

The Scheduler understands two main primitives: Events and Tasks.  Each stanza
in the config file specifies a Task that triggers on a given Event.

Events:
  The scheduler supports two kinds of Events: timed events, and
  build system events -- like a particular build artifact becoming available.
  Every Event has a set of Tasks that get run whenever the event happens.

Tasks:
  Basically, event handlers.  A Task is specified in the config file like so:
  [NightlyPower]
  suite: power
  run_on: nightly
  pool: remote_power
  branch_spec: >=R20,factory

  This specifies a Task that gets run whenever the 'nightly' event occurs.
  The Task schedules a suite of tests called 'power' on the pool of machines
  called 'remote_power', for both the factory branch and all active release
  branches from R20 on.


On startup, the scheduler reads in a config file that provides a few
parameters for certain supported Events (the time/day of the 'weekly'
and 'nightly' triggers, for example), and configures all the Tasks
that will be in play.
"""

import logging, optparse, os, re, signal, sys
import common
import board_enumerator, deduping_scheduler, driver, forgiving_config_parser
import manifest_versions
from autotest_lib.client.common_lib import logging_config, logging_manager
from autotest_lib.server.cros import frontend_wrappers


def signal_handler(signal, frame):
    logging.info('Signal %d received.  Exiting gracefully...', signal)
    sys.exit(0)


class SchedulerLoggingConfig(logging_config.LoggingConfig):
    @classmethod
    def get_log_name(cls):
        return cls.get_timestamped_log_name('suite_scheduler')


    def configure_logging(self, log_dir=None):
        super(SchedulerLoggingConfig, self).configure_logging(use_console=True)

        if not log_dir:
            return
        logfile_name = self.get_log_name()

        self.add_file_handler(logfile_name, logging.DEBUG, log_dir=log_dir)


def parse_options():
    usage = "usage: %prog [options]"
    parser = optparse.OptionParser(usage=usage)
    parser.add_option('-f', '--config_file', dest='config_file',
                      metavar='/path/to/config', default='suite_scheduler.ini',
                      help='Scheduler config. Defaults to suite_scheduler.ini')
    parser.add_option('-e', '--events', dest='events',
                      metavar='list,of,events',
                      help='Handle listed events once each, then exit.  '\
                        'Must also specify a build to test.')
    parser.add_option('-i', '--build', dest='build',
                      help='If handling a list of events, the build to test.'\
                        ' Ignored otherwise.')
    parser.add_option('-d', '--log_dir', dest='log_dir',
                      help='Log to a file in the specified directory.')
    parser.add_option('-l', '--list_events', dest='list',
                      action='store_true', default=False,
                      help='List supported events and exit.')
    options, args = parser.parse_args()
    return parser, options, args


def main():
    signal.signal(signal.SIGINT, signal_handler)
    signal.signal(signal.SIGHUP, signal_handler)
    signal.signal(signal.SIGTERM, signal_handler)

    parser, options, args = parse_options()
    if args or options.events and not options.build:
        parser.print_help()
        return 1

    if options.config_file and not os.path.exists(options.config_file):
        logging.error('Specified config file %s does not exist.',
                      options.config_file)
        return 1

    logging_manager.configure_logging(SchedulerLoggingConfig(),
                                      log_dir=options.log_dir)
    if not options.log_dir:
        logging.info('Not logging to a file, as --log_dir was not passed.')

    config = forgiving_config_parser.ForgivingConfigParser()
    config.read(options.config_file)

    afe = frontend_wrappers.RetryingAFE(timeout_min=1, delay_sec=5, debug=False)
    enumerator = board_enumerator.BoardEnumerator(afe)
    scheduler = deduping_scheduler.DedupingScheduler(afe)
    mv = manifest_versions.ManifestVersions()
    d = driver.Driver(scheduler, enumerator)
    d.SetUpEventsAndTasks(config, mv)

    if options.events:
        # Act as though listed events have just happened.
        keywords = re.split('\s*,\s*', options.events)
        logging.info('Forcing events: %r' % keywords)
        d.ForceEventsOnceForBuild(keywords, options.build)
    else:
        mv.Initialize()
        d.RunForever(mv)


if __name__ == "__main__":
    sys.exit(main())
