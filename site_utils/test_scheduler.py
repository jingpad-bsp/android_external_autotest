#!/usr/bin/python
#
# Copyright (c) 2012 The Chromium OS Authors. All rights reserved.
# Use of this source code is governed by a BSD-style license that can be
# found in the LICENSE file.

"""Tool for scheduling BVT and full suite testing of Chrome OS images.

Test Scheduler is a tool for scheduling the testing of Chrome OS images across
multiple boards and platforms. All testing is driven through a board to platform
mapping specified in a JSON config file.

For each board, platform tuple the bvt group is scheduled. Once the bvt has
completed and passed, all groups from 'default_full_groups' are scheduled.

Test Scheduler expects the JSON config file to be in the current working
directory or to be run with --config pointing to the actual config file.
"""

__author__ = 'dalecurtis@google.com (Dale Curtis)'

import logging
import optparse
import os
import re
import tempfile

from chromeos_test import autotest_util
from chromeos_test import common_util
from chromeos_test import dash_util
from chromeos_test import dev_server
from chromeos_test import log_util
from chromeos_test import test_config

# Autotest imports

import common

from autotest_lib.client.common_lib.cros import dev_server as new_dev_server


# RegEx for extracting versions from build strings.
_3_TUPLE_VERSION_RE = re.compile('R\d+-(\d+\.\d+\.\d+)')
_4_TUPLE_VERSION_RE = re.compile('(\d+\.\d+\.\d+\.\d+)+-')


def _ParseVersion(build):
  """Extract version from build string. Parses x.x.x.x* and Ryy-x.x.x* forms."""
  match = _3_TUPLE_VERSION_RE.match(build)
  if not match:
    match = _4_TUPLE_VERSION_RE.match(build)

  # Will generate an exception if no match was found.
  return match.group(1)


class TestRunner(object):
  """Helper class for scheduling jobs from tests and groups."""

  def __init__(self, board, build, cli, config, dev, new_dev, upload=False):
    """Initializes class variables.

    Args:
      board: Board name for this build; e.g., x86-generic-rel
      build: Full build string to look for; e.g., 0.8.61.0-r1cf43296-b269
      cli: Path to Autotest CLI.
      config: Dictionary of configuration as loaded from JSON.
      dev: An initialized DevServer() instance.
      new_dev: new dev_server interface under client/common_lib/cros.
      upload: Whether to upload created job information to appengine.
    """
    self._board = board
    self._build = build
    self._config = config
    self._cli = cli
    self._dev = dev
    self._new_dev = new_dev
    self._upload = upload

  def RunTest(self, job_name, platform, test, build=None, control_mods=None):
    """Given a test dictionary: retrieves control file and creates jobs.

    Test dictionary format is as follows:

        {'name': '', 'control': '', 'count': ##, 'labels': [...], 'sync': <T/F>}

    Optional keys are count, labels, and sync. If not specified they will be set
    to default values of 1, None, and False respectively.

    Jobs are created with the name <board>-<build>_<name>.

    Args:
      job_name: Name of job to create.
      platform: Platform to schedule job for.
      test: Test config dictionary.
      build: Build to use, if different than the one used to initialize class.
      control_mods: List of functions to call for control file preprocessing.
          Each function will be passed the contents of the control file.

    Raises:
      common_util.ChromeOSTestError: If any steps fail.
    """
    # Initialize defaults for optional keys. Avoids tedious, if <key> in <test>
    default = {'count': 1, 'labels': None, 'sync': None}
    default.update(test)
    test = default

    if test['sync']:
      test['sync'] = test['count']

    if not build:
      build = self._build

    # Pull control file from Dev Server.
    try:
      # Use new style for TOT boards.
      if 'release' in self._board:
        image = '%s/%s' % (self._board, build)
        # Make sure the latest board is already staged. This will hang until
        # the image is properly staged or return immediately if it is already
        # staged. This will have little impact on the rest of this process and
        # ensures we properly launch tests while straddling the old and the new
        # styles.
        self._new_dev.trigger_download(image)
        control_file_data = self._new_dev.get_control_file(image,
                                                           test['control'])
        if 'Unknown control path' in control_file_data:
          raise common_util.ChromeOSTestError(
              'Control file %s not yet staged, skipping' % test['control'])
      else:
        control_file_data = self._dev.GetControlFile(self._board, build,
                                                     test['control'])
    except (new_dev_server.DevServerException, common_util.ChromeOSTestError):
      logging.error('Missing %s for %s on %s.', test['control'], job_name,
                    platform)
      raise

    # If there's any preprocessing to be done call it now.
    if control_mods:
      for mod in control_mods:
        control_file_data = mod(control_file_data)

    # Create temporary file and write control file contents to it.
    temp_fd, temp_fn = tempfile.mkstemp()
    os.write(temp_fd, control_file_data)
    os.close(temp_fd)

    # Create Autotest job using control file and image parameter.
    try:
      # Inflate the priority of BVT runs.
      if job_name.endswith('_bvt'):
        priority = 'urgent'
      else:
        priority = 'medium'

      # Add pool:suites to all jobs to avoid using the BVT machines with the
      # same platform label.
      if test['labels'] is None:
        test['labels'] = ['pool:suites']
      else:
         test['labels'].append('pool:suites')

      job_id = autotest_util.CreateJob(
          name=job_name, control=temp_fn,
          platforms='%d*%s' % (test['count'], platform), labels=test['labels'],
          sync=test['sync'],
          update_url=self._dev.GetUpdateUrl(self._board, build),
          cli=self._cli, priority=priority)
    finally:
      # Cleanup temporary control file. Autotest doesn't need it anymore.
      os.unlink(temp_fn)

    #TODO(dalecurtis): Disabled, since it's not under active development.
    #try:
    #  appengine_cfg = self._config.get('appengine', {})
    #  if self._upload and appengine_cfg:
    #    dash_util.UploadJob(appengine_cfg, job_id)
    #except common_util.ChromeOSTestError:
    #  logging.warning('Failed to upload job to AppEngine.')

  def RunTestGroups(self, groups, platform, lock=True):
    """Given a list of test groups, creates Autotest jobs for associated tests.

    Given a list of test groups, map each into the "groups" dictionary from the
    JSON configuration file and launch associated tests. If lock is specified it
    will attempt to acquire a dev server lock for each group before starting. If
    a lock can't be obtained, the group won't be started.

    Args:
      groups: List of group names to run tests for. See test config for valid
          group names.
      platform: Platform label to look for. See test config for valid platforms.
      lock: Attempt to acquire lock before running tests?
    """
    for group in groups:
      if not group in self._config['groups']:
        logging.warning('Skipping unknown group "%s".', group)
        continue

      # Start tests for the given group.
      for test in self._config['groups'][group]:
        has_lock = False
        try:
          job_name = '%s-%s_%s' % (self._board, self._build, test['name'])

          # Attempt to acquire lock for test.
          if lock:
            tag = '%s/%s/%s_%s_%s' % (self._board, self._build, platform,
                                      group, test['name'])
            try:
              self._dev.AcquireLock(tag)
              has_lock = True
            except common_util.ChromeOSTestError, e:
              logging.debug('Refused lock for test "%s" from group "%s".'
                            ' Assuming it has already been started.',
                            test['name'], group)
              continue

          self.RunTest(platform=platform, test=test, job_name=job_name)
          logging.info('Successfully created job "%s".', job_name)
        except common_util.ChromeOSTestError, e:
          logging.exception(e)
          logging.error('Failed to schedule test "%s" from group "%s".',
                        test['name'], group)

          # We failed, so release lock and let next run pick this test up.
          if has_lock:
            self._dev.ReleaseLock(tag)

  def RunAutoupdateTests(self, platform):
    # Process the autoupdate targets.
    for target in self._dev.ListAutoupdateTargets(self._board, self._build):
      has_lock = False
      try:
        # Tell other instances of the scheduler we're processing this target.
        tag = '%s/%s/%s_%s' % (self._board, self._build, platform['platform'],
                               target)
        try:
          self._dev.AcquireLock(tag)
          has_lock = True
        except common_util.ChromeOSTestError, e:
          logging.debug('Refused lock for autoupdate target "%s". Assuming'
                        ' it has already been started.', target)
          continue

        # Split target into base build and convenience label.
        base_build, label = target.split('_')

        # Setup preprocessing function to insert the correct update URL into
        # the control file.
        control_preprocess_fn = lambda x: x % {'update_url': '%s/%s/%s' % (
            self._dev.GetUpdateUrl(
                self._board, self._build), self._dev.AU_BASE, target)}

        # E.g., x86-mario-r14-0.14.734.0_to_0.14.734.0-a1-b123_nton_au
        job_name = '%s-%s_to_%s_%s_au' % (
            self._board, _ParseVersion(base_build), self._build, label)

        self.RunTest(
            platform=platform['platform'],
            test=self._config['groups']['autoupdate'][0], job_name=job_name,
            build=base_build,
            control_mods=[control_preprocess_fn])
        logging.info('Successfully created job "%s".', job_name)
      except common_util.ChromeOSTestError, e:
        logging.exception(e)
        logging.error('Failed to schedule autoupdate target "%s".', target)

        # We failed, so release lock and let next run pick this target up.
        if has_lock:
          self._dev.ReleaseLock(tag)


def ParseOptions():
  """Parse command line options. Returns 2-tuple of options and config."""
  parser = optparse.OptionParser('usage: %prog [options]')

  # Add utility/helper class command line options.
  test_config.AddOptions(parser)
  log_util.AddOptions(parser)
  autotest_util.AddOptions(parser, cli_only=True)

  options = parser.parse_args()[0]
  config = test_config.TestConfig(options.config)

  return options, config.GetConfig()


def main():
  options, config = ParseOptions()

  # Setup logger and enable verbose mode if specified.
  log_util.InitializeLogging(options.verbose)

  # Initialize Dev Server Utility class.
  dev = dev_server.DevServer(**config['dev_server'])

  # Main processing loop. Look for new builds of each board.
  for board in config['boards']:
    for platform in config['boards'][board]['platforms']:
      logging.info('----[ Processing board %s, platform %s ]----',
                   board, platform['platform'])
      try:
        new_dev = new_dev_server.DevServer()
        # The variable board is akin to target in the new nomenclature. This is
        # the old style and the new style clashing.
        # TODO(scottz): remove kludge once we move to suite scheduler.
        for milestone in ['r19', 'r20']:
          try:
            build = new_dev.get_latest_build(board, milestone=milestone)
          except new_dev_server.DevServerException:
            continue
          # Leave just in case we do get an empty response from the server
          # but we shouldn't.
          if not build:
            continue
          test_runner = TestRunner(
              board=board, build=build, cli=options.cli, config=config,
              dev=dev, new_dev=new_dev, upload=True)

          # Determine which groups to run.
          full_groups = []
          if 'groups' in platform:
            full_groups += platform['groups']
          else:
            # Add default groups to the job since 'groups' was not defined.
            # if test_suite is set to True use 'default_tot_groups' from the
            # json configuration, otherwise use 'default_groups.'
            if platform.get('test_suite'):
              full_groups += config['default_tot_groups']
            else:
              full_groups += config['default_groups']

            if 'extra_groups' in platform:
              full_groups += platform['extra_groups']

          test_runner.RunTestGroups(
              groups=full_groups, platform=platform['platform'])

          # Skip platforms which are not marked for AU testing.
          if not platform.get('au_test', False):
            continue

          # Process AU targets.
          test_runner.RunAutoupdateTests(platform)
      except (new_dev_server.DevServerException,
              common_util.ChromeOSTestError) as e:
        logging.exception(e)
        logging.warning('Exception encountered during processing. Skipping.')


if __name__ == '__main__':
  main()
