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
  branch_specs: >=R20,factory

  This specifies a Task that gets run whenever the 'nightly' event occurs.
  The Task schedules a suite of tests called 'power' on the pool of machines
  called 'remote_power', for both the factory branch and all active release
  branches from R20 on.


On startup, the scheduler reads in a config file that provides a few
parameters for certain supported Events (the time/day of the 'weekly'
and 'nightly' triggers, for example), and configures all the Tasks
that will be in play.
"""

import getpass, logging, logging.handlers, optparse, os, re, signal, sys
import traceback
import common
import board_enumerator, deduping_scheduler, driver, forgiving_config_parser
import manifest_versions, sanity
from autotest_lib.client.common_lib import global_config
from autotest_lib.client.common_lib import logging_config, logging_manager
from autotest_lib.server.cros.dynamic_suite import frontend_wrappers


CONFIG_SECTION = 'SCHEDULER'

CONFIG_SECTION_SMTP = 'SERVER'


def signal_handler(signal, frame):
    """Singnal hanlder to exit gracefully.

    @param signal: signum
    @param frame: stack frame object
    """
    logging.info('Signal %d received.  Exiting gracefully...', signal)
    sys.exit(0)


class SeverityFilter(logging.Filter):
    """Filters out messages of anything other than self._level"""
    def __init__(self, level):
        self._level = level


    def filter(self, record):
        """Causes only messages of |self._level| severity to be logged."""
        return record.levelno == self._level


class SchedulerLoggingConfig(logging_config.LoggingConfig):
    """Configure loggings for scheduler, e.g., email setup."""
    def __init__(self):
        super(SchedulerLoggingConfig, self).__init__()
        self._from_address = global_config.global_config.get_config_value(
                CONFIG_SECTION, "notify_email_from", default=getpass.getuser())

        self._notify_address = global_config.global_config.get_config_value(
                CONFIG_SECTION, "notify_email",
                default='chromeos-lab-admins@google.com')

        self._smtp_server = global_config.global_config.get_config_value(
                CONFIG_SECTION_SMTP, "smtp_server", default='localhost')

        self._smtp_port = global_config.global_config.get_config_value(
                CONFIG_SECTION_SMTP, "smtp_port", default=None)

        self._smtp_user = global_config.global_config.get_config_value(
                CONFIG_SECTION_SMTP, "smtp_user", default='')

        self._smtp_password = global_config.global_config.get_config_value(
                CONFIG_SECTION_SMTP, "smtp_password", default='')


    @classmethod
    def get_log_name(cls):
        """Get timestamped log name of suite_scheduler, e.g.,
        suite_scheduler.log.2013-2-1-02-05-06.

        @param cls: class
        """
        return cls.get_timestamped_log_name('suite_scheduler')


    def add_smtp_handler(self, subject, level=logging.ERROR):
        """Add smtp handler to logging handler to trigger email when logging
        occurs.

        @param subject: email subject.
        @param level: level of logging to trigger smtp handler.
        """
        if not self._smtp_user or not self._smtp_password:
            creds = None
        else:
            creds = (self._smtp_user, self._smtp_password)
        server = self._smtp_server
        if self._smtp_port:
            server = (server, self._smtp_port)

        handler = logging.handlers.SMTPHandler(server,
                                               self._from_address,
                                               [self._notify_address],
                                               subject,
                                               creds)
        handler.setLevel(level)
        # We want to send mail for the given level, and only the given level.
        # One can add more handlers to send messages for other levels.
        handler.addFilter(SeverityFilter(level))
        handler.setFormatter(
            logging.Formatter('%(asctime)s %(levelname)-5s %(message)s'))
        self.logger.addHandler(handler)
        return handler


    def configure_logging(self, log_dir=None):
        super(SchedulerLoggingConfig, self).configure_logging(use_console=True)

        if not log_dir:
            return
        base = self.get_log_name()

        self.add_file_handler(base + '.DEBUG', logging.DEBUG, log_dir=log_dir)
        self.add_file_handler(base + '.INFO', logging.INFO, log_dir=log_dir)
        self.add_smtp_handler('Suite scheduler ERROR', logging.ERROR)
        self.add_smtp_handler('Suite scheduler WARNING', logging.WARN)


def parse_options():
    """Parse commandline options."""
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
    parser.add_option('-t', '--sanity', dest='sanity', action='store_true',
                      default=False,
                      help="Check the config file for any issues.")
    parser.add_option('-b', '--file_bug', dest='file_bug', action='store_true',
                      default=False,
                      help="File bugs for known suite scheduling exceptions.")

    options, args = parser.parse_args()
    return parser, options, args


def main():
    """Entry point for suite_scheduler.py"""
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

    config = forgiving_config_parser.ForgivingConfigParser()
    config.read(options.config_file)

    if options.list:
        print 'Supported events:'
        for event_class in driver.Driver.EVENT_CLASSES:
            print '  ', event_class.KEYWORD
        return 0

    # If we're just sanity checking, we can stop after we've parsed the
    # config file.
    if options.sanity:
        # config_file_getter generates a high amount of noise at DEBUG level
        logging.getLogger().setLevel(logging.WARNING)
        d = driver.Driver(None, None)
        d.SetUpEventsAndTasks(config, None)
        tasks_per_event = d.TasksFromConfig(config)
        # flatten [[a]] -> [a]
        tasks = [x for y in tasks_per_event.values() for x in y]
        control_files_exist = sanity.CheckControlFileExistance(tasks)
        return control_files_exist

    logging_manager.configure_logging(SchedulerLoggingConfig(),
                                      log_dir=options.log_dir)
    if not options.log_dir:
        logging.info('Not logging to a file, as --log_dir was not passed.')

    afe = frontend_wrappers.RetryingAFE(timeout_min=1, delay_sec=5, debug=False)
    enumerator = board_enumerator.BoardEnumerator(afe)
    scheduler = deduping_scheduler.DedupingScheduler(afe, options.file_bug)
    mv = manifest_versions.ManifestVersions()
    d = driver.Driver(scheduler, enumerator)
    d.SetUpEventsAndTasks(config, mv)

    try:
        if options.events:
            # Act as though listed events have just happened.
            keywords = re.split('\s*,\s*', options.events)
            logging.info('Forcing events: %r', keywords)
            d.ForceEventsOnceForBuild(keywords, options.build)
        else:
            mv.Initialize()
            d.RunForever(config, mv)
    except Exception as e:
        logging.error('Fatal exception in suite_scheduler: %r\n%s', e,
                      traceback.format_exc())
        return 1

if __name__ == "__main__":
    sys.exit(main())
