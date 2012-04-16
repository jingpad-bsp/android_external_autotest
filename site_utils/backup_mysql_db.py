#!/usr/bin/python

# Copyright (c) 2012 The Chromium OS Authors. All rights reserved.
# Use of this source code is governed by a BSD-style license that can be
# found in the LICENSE file.

"""Module used to back up the mysql db and upload to Google Storage.

Usage:
  backup_mysql_db.py --type=weekly --gs_bucket=gs://my_bucket --keep 10

  gs_bucket may refer to a local location by omitting gs:// and giving a local
  path if desired for testing. The example usage above creates a dump
  of the autotest db, uploads it to gs://my_bucket/weekly/dump_file.date and
  cleans up older dumps if there are more than 10 in that directory.
"""

import datetime
from distutils import version
import logging
import optparse
import os
import tempfile

import common

from autotest_lib.client.common_lib import error
from autotest_lib.client.common_lib import global_config, logging_manager, utils
from autotest_lib.utils import test_importer


_ATTEMPTS = 3
_GSUTIL_BIN = 'gsutil'
_GS_BUCKET = 'gs://chromeos-lab/backup/database'


_DAILY = 'daily'
_WEEKLY = 'weekly'
_MONTHLY = 'monthly'
_SCHEDULER_TYPES = [_DAILY, _WEEKLY, _MONTHLY]


class MySqlArchiver(object):
    """Class that archives the Autotest MySQL DB to Google Storage.

    Vars:
      gs_dir:  The path to the directory in Google Storage that this dump file
               will be uploaded to.
      number_to_keep:  The number of dumps we should store.
    """


    def __init__(self, scheduled_type, number_to_keep, gs_bucket):
        self._gs_dir = '/'.join([gs_bucket, scheduled_type])
        self._number_to_keep = number_to_keep


    @staticmethod
    def _get_user_pass():
        """Returns a tuple containing the user/pass to use to access the DB."""
        user = global_config.global_config.get_config_value(
                'CROS', 'db_backup_user')
        password = global_config.global_config.get_config_value(
                'CROS', 'db_backup_password')
        return user, password


    def create_mysql_dump(self):
        """Returns the path to a mysql dump of the current autotest DB."""
        user, password = self._get_user_pass()
        _, filename = tempfile.mkstemp('autotest_db_dump')
        logging.debug('Dumping mysql database to file %s', filename)
        utils.system('set -o pipefail; mysqldump --all-databases --user=%s '
                     '--password=%s | gzip - > %s' % (user, password, filename))
        return filename


    @staticmethod
    def _get_name():
        """Returns the name to use for this mysql dump."""
        return 'autotest-dump.%s.gz' % (
                datetime.datetime.now().strftime('%y.%m.%d'))


    @staticmethod
    def _retry_run(cmd):
        """Run the specified |cmd| string, retrying if necessary.

        Args:
          cmd: The command to run.
        """
        for attempt in range(_ATTEMPTS):
            try:
                return utils.system_output(cmd)
            except error.CmdError:
                if attempt == _ATTEMPTS - 1:
                    raise
                else:
                    logging.error('Failed to run %r', cmd)


    def upload_to_google_storage(self, dump_file):
        """Uploads the given |dump_file| to Google Storage."""
        cmd = '%(gs_util)s cp %(dump_file)s %(gs_dir)s/%(name)s'
        input_dict = dict(gs_util=_GSUTIL_BIN, dump_file=dump_file,
                          name=self._get_name(), gs_dir=self._gs_dir)
        cmd = cmd % input_dict
        logging.debug('Uploading mysql dump to google storage')
        self._retry_run(cmd)
        os.remove(dump_file)


    def _get_gs_command(self, cmd):
        """Returns an array representing the command for rm or ls."""
        # Helpful code to allow us to test without gs.
        assert cmd in ['rm', 'ls']
        gs_bin = _GSUTIL_BIN
        if self._gs_dir.startswith('gs://'):
            cmd_array = [gs_bin, cmd]
        else:
            cmd_array = [cmd]

        return cmd_array


    def _do_ls(self):
        """Returns the output of running ls on the gs bucket."""
        cmd = self._get_gs_command('ls') + [self._gs_dir]
        return self._retry_run(' '.join(cmd))


    def cleanup(self):
        """Cleans up the gs bucket to ensure we don't over archive."""
        logging.debug('Cleaning up previously archived dump files.')
        listing = self._do_ls()
        ordered_listing = sorted(listing.splitlines(), key=version.LooseVersion)
        if len(ordered_listing) < self._number_to_keep:
            logging.debug('Cleanup found nothing to do.')
            return

        to_remove = ordered_listing[:-self._number_to_keep]
        rm_cmd = self._get_gs_command('rm')
        for artifact in to_remove:
            cmd = ' '.join(rm_cmd + [self._gs_dir + '/' + artifact])
            self._retry_run(cmd)


def parse_options():
    """Parses given options."""
    parser = optparse.OptionParser()
    parser.add_option('--gs_bucket', default=_GS_BUCKET,
                      help='Google storage bucket to store mysql db dumps.')
    parser.add_option('--keep', default=10, type=int,
                      help='Number of dumps to keep of specified type.')
    parser.add_option('--type', default=_DAILY,
                      help='The type of mysql dump to store.')
    parser.add_option('--verbose', default=False, action='store_true',
                      help='Google storage bucket to store mysql db dumps.')
    options = parser.parse_args()[0]
    if options.type not in _SCHEDULER_TYPES:
        parser.error('Type must be either: %s.' % ', '.join(_SCHEDULER_TYPES))

    return options


def main():
    """Runs the program."""
    options = parse_options()
    logging_manager.configure_logging(test_importer.TestImporterLoggingConfig(),
                                      verbose=options.verbose)
    archiver = MySqlArchiver(options.type, options.keep, options.gs_bucket)
    dump_file = archiver.create_mysql_dump()
    archiver.upload_to_google_storage(dump_file)
    archiver.cleanup()


if __name__ == '__main__':
    main()
