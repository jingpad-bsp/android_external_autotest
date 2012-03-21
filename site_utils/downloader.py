#!/usr/bin/python
#
# Copyright (c) 2011 The Chromium OS Authors. All rights reserved.
# Use of this source code is governed by a BSD-style license that can be
# found in the LICENSE file.

"""Tool for downloading and processing the latest Buildbot builds.

Downloader is a tool for downloading and processing images for the various board
types supported by ChromeOS.

All downloading and processing is driven by a board to archive server mapping in
a specified JSON config file. Boards are processed sequentially.

Downloader is multi-instance friendly. You can spin up as many instances as
necessary to handle image processing load (which can be substantial). It is not
recommended to run more than one instance per machine.

Downloader expects the JSON config file to be in the current working directory
or to be run with --config pointing to the actual config file.
"""

__author__ = 'dalecurtis@google.com (Dale Curtis)'

import logging
import optparse
import os
import re
import shutil

from chromeos_test import autotest_util
from chromeos_test import build_util
from chromeos_test import common_util
from chromeos_test import dash_util
from chromeos_test import dev_server
from chromeos_test import log_util
from chromeos_test import test_config

# Autotest imports

import common

from autotest_lib.client.common_lib.cros import dev_server as new_dev_server


# Default location of ChromeOS source checkout.
DEFAULT_CROS_PATH = os.path.join('/usr/local/google/home',
                                 os.environ['USER'], 'chromeos/chromeos')


class Downloader(object):
  """Main class for Downloader. All the magic happens in ProcessBoards()."""

  def __init__(self, options, config):
    """Inits Downloader class with options and config data structures.

    Args:
      options: Command line options packages as created by ParseOptions().
      config: Dictionary of configuration as loaded from JSON.
    """
    self._options = options
    self._config = config

  def ProcessBoards(self):
    """For each board: find latest build version, create components, and upload.

    The main processing function for the Downloader class. Given a configuration
    mapping between boards and locations it will:

      - Find the latest version of a build for a given board.
      - Determine if the build already exists on Dev Server.
      - Download and extract the build to a staging directory.
      - Convert binary testing image into relevant components.
      - Upload components to Dev Server.
    """
    # Initialize boards listing. If user has specified a board and it's valid,
    # only process that board.
    boards = self._config['boards']
    if self._options.board and self._options.board in boards:
      boards = {self._options.board: boards[self._options.board]}

    # Initialize Dev Server utility class.
    dev = dev_server.DevServer(**self._config['dev_server'])
    new_dev = new_dev_server.DevServer()

    # Main processing loop. Look for new builds of each board.
    for board in boards:
      # |board| is the same as target in the new nomenclature, i.e.
      # x86-alex-release. this also uses old style; R18, R16, etc.
      board_cfg = boards[board]
      board_cfg.setdefault('archive_path', None)
      board_cfg.setdefault('build_pattern', None)
      board_cfg.setdefault('boto', None)
      board_cfg.setdefault('import_tests', False)
      if not board_cfg.get('archive_server'):
        logging.info('Skipping %s, devserver handles the download.', board)
        continue

      # Bind remote_dir and staging_dir here so we can tell if we need to do any
      # cleanup after an exception occurs before remote_dir is set.
      remote_dir = staging_dir = None
      try:
        logging.info('------------[ Processing board %s ]------------', board)
        # Retrieve the latest build version for this board.
        if not self._options.build:
          build = build_util.GetLatestBuildbotBuildVersion(
              archive_server=board_cfg['archive_server'], board=board,
              boto=board_cfg['boto'], archive_path=board_cfg['archive_path'],
              build_pattern=board_cfg['build_pattern'])

          if not build:
            logging.info('Bad build version returned from server. Skipping.')
            continue

          logging.info('Latest build available on Buildbot is %s .', build)
        else:
          build = self._options.build

        if board_cfg.get('download_devserver'):
          # Use new dev server download pathway for staging image.
          image = '%s/%s' % (board, build)
          logging.info('Downloading %s using the dev server.', image)
          new_dev.trigger_download(image)
          continue

        # Create Dev Server directory for this build and tell other Downloader
        # instances we're working on this build.
        try:
          remote_dir = dev.AcquireLock('/'.join([board, build]))
        except common_util.ChromeOSTestError:
          # Label as info instead of error because this will be the most common
          # end point for the majority of runs.
          logging.info('Refused lock for build. Assuming build has already been'
                       ' processed.')
          continue

        # Download and extract build to a temporary directory or process the
        # build at the user specified staging directory.
        if not self._options.staging:
          logging.info('Downloading build from %s/%s',
                       board_cfg['archive_server'], board)

          staging_dir, archive_path = build_util.DownloadAndExtractBuild(
              archive_server=board_cfg['archive_server'],
              archive_path=board_cfg['archive_path'], board=board,
              boto=board_cfg['boto'], build=build)

        else:
          staging_dir = self._options.staging

        # Do we need to import tests?
        if board_cfg['import_tests'] and not autotest_util.ImportTests(
            hosts=self._config['import_hosts'], staging_dir=staging_dir):
          logging.warning('One or more hosts failed to import tests!')

        # Process build and create update.gz and stateful.image.gz
        logging.info('Creating build components under %s', staging_dir)
        build_util.CreateBuildComponents(
            staging_dir=staging_dir, cros_checkout=self._options.cros_checkout)

        # Generate N->N AU payload.
        nton_payload_dir = None
        try:
          nton_payload_dir = os.path.join(dev.AU_BASE, build + '_nton')
          common_util.MakedirsExisting(
              os.path.join(staging_dir, nton_payload_dir))

          build_util.CreateUpdateZip(
              cros_checkout=self._options.cros_checkout,
              staging_dir=staging_dir, output_dir=nton_payload_dir,
              source_image=build_util.TEST_IMAGE)
        except common_util.ChromeOSTestError, e:
          if nton_payload_dir:
            shutil.rmtree(os.path.join(staging_dir, nton_payload_dir))
          logging.exception(e)

        # Generate N-1->N AU payload.
        mton_payload_dir = None
        try:
          # Retrieve N-1 (current LATEST) build from Dev Server.
          previous_build = dev.GetLatestBuildVersion(board)
          previous_image = dev.GetImage(board, previous_build, staging_dir)

          mton_payload_dir = os.path.join(dev.AU_BASE, previous_build + '_mton')
          common_util.MakedirsExisting(
              os.path.join(staging_dir, mton_payload_dir))

          build_util.CreateUpdateZip(
              cros_checkout=self._options.cros_checkout,
              staging_dir=staging_dir, output_dir=mton_payload_dir,
              source_image=previous_image)
        except common_util.ChromeOSTestError, e:
          if mton_payload_dir:
            shutil.rmtree(os.path.join(staging_dir, mton_payload_dir))
          logging.exception(e)

        # TODO(dalecurtis): Sync official chromeos_test_image.bins.

        # TODO(dalecurtis): Generate <official>->N AU payloads.

        # Upload required components into jailed Dev Server.
        logging.info('Uploading build components to Dev Server.')
        dev.UploadBuildComponents(staging_dir=staging_dir, upload_image=True,
                                  remote_dir=remote_dir)

        # Create and upload LATEST file to the Dev Server.
        if not self._options.build:
          dev.UpdateLatestBuild(board=board, build=build)

          #TODO(dalecurtis): Disabled, since it's not under active development.
          #appengine_cfg = self._config.get('appengine', {})
          #if appengine_cfg:
          #  dash_util.UploadBuild(appengine_cfg, board, build, archive_path)
        else:
          logging.warning('LATEST file not updated because --build was '
                          'specified. Make sure you manually update the LATEST '
                          'file if required.')
      except Exception, e:
        logging.exception(e)

        # Release processing lock, which will remove build components directory
        # so future runs can retry.
        if remote_dir:
          try:
            dev.ReleaseLock('/'.join([board, build]))
          except (KeyboardInterrupt, common_util.ChromeOSTestError):
            logging.critical('Failed to clean up Dev Server after failed run on'
                             ' build %s.', build)

        # If Exception was a ^C, break out of processing loop.
        if isinstance(e, KeyboardInterrupt):
          break
        if not isinstance(e, common_util.ChromeOSTestError):
          raise
      finally:
        # Always cleanup after ourselves. As an automated system with firm
        # inputs, it's trivial to recreate error conditions manually. Where as
        # repeated failures over a long weekend could bring the system down.
        if staging_dir:
          # Remove the staging directory.
          logging.info('Cleaning up staging directory %s', staging_dir)
          cmd = 'sudo rm -rf ' + staging_dir
          msg = 'Failed to clean up staging directory!'
          common_util.RunCommand(cmd=cmd, error_msg=msg)


def ParseOptions():
  """Parse command line options. Returns 2-tuple of options and config."""
  # If default config exists, parse it and use values for help screen.
  config = test_config.TestConfig()

  # If config is provided parse values to make help screen more useful.
  boards = config.ParseConfigGroups()[0]

  parser = optparse.OptionParser('usage: %prog [options]')

  parser.add_option('--board', dest='board',
                    help='Process only the specified board. Valid boards: %s'
                    % boards)
  parser.add_option('--build', dest='build',
                    help=('Specify the build version to process. Must be used '
                          'with the --board option. LATEST file will not be '
                          'updated with this option.'))
  parser.add_option('--cros_checkout', dest='cros_checkout',
                    default=DEFAULT_CROS_PATH,
                    help=('Location of ChromeOS source checkout. Defaults to '
                          '"%default".'))
  parser.add_option('--staging', dest='staging',
                    help=('Specify a pre-populated staging directory. Must be '
                          'used with the --board and --build options. Useful '
                          'to finish a run that was interrupted or failed.'))

  # Add utility/helper class command line options.
  test_config.AddOptions(parser)
  log_util.AddOptions(parser)

  options = parser.parse_args()[0]

  if options.build and not options.board:
    parser.error('If --build is used, --board must be specified as well.')

  if options.staging and not (options.board and options.build):
    parser.error(('If --staging is used, --board and --build must be'
                  ' specified as well.'))

  # Load correct config file if alternate is specified.
  if options.config != test_config.DEFAULT_CONFIG_FILE:
    config = test_config.TestConfig(options.config)
    boards = config.ParseConfigGroups()[0]

  if options.board and not options.board in boards:
    parser.error('Invalid board "%s" specified. Valid boards are: %s'
                 % (options.board, boards))

  return options, config.GetConfig()


def main():
  # Parse options and load config.
  options, config = ParseOptions()

  # Setup logger and enable verbose mode if specified.
  log_util.InitializeLogging(options.verbose)

  Downloader(options=options, config=config).ProcessBoards()


if __name__ == '__main__':
  main()
