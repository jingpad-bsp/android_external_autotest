#!/usr/bin/python
#
# Copyright (c) 2011 The Chromium OS Authors. All rights reserved.
# Use of this source code is governed by a BSD-style license that can be
# found in the LICENSE file.

"""Script to run an Autotest job on machines in a remote lab.

Takes an image. Verifies the image to be a test image (we need SSH access). Then
splits the image into update.gz and stateful.tgz components. Finally, uploads
the components to a Dev Server in the lab.

Once everything is in the necessary places a job is scheduled using the Autotest
command line tools on /home/build/static and URL returned to the user.
"""

__author__ = 'dalecurtis@google.com (Dale Curtis)'
__version__ = 'v1.3'

import json
import logging
import optparse
import os
import sys
import tempfile

import chromeos_test_common
from chromeos_test import autotest_util
from chromeos_test import build_util
from chromeos_test import common_util
from chromeos_test import test_config
from chromeos_test.colors import Colors
from chromeos_test.dev_server import DevServer


# Autotest directory relative to CrOS root.
DEFAULT_AUTOTEST_DIR = 'src/third_party/autotest/files'

# Location of default board file.
DEFAULT_BOARD_FILE = 'src/scripts/.default_board'

# Root of Chrome OS checkout should be up a few directories relative to us.
DEFAULT_CROS_DIR = chromeos_test_common.CROS_DIR

# Root of the default build directory relative to CrOS root.
DEFAULT_IMAGE_DIR = 'src/build/images'

# Tag prefix for Dev builds.
DEV_BUILD_PREFIX = 'dev'

LAB_TEST_CONFIG = os.path.join(chromeos_test_common.CURRENT_DIR,
                               'lab_test.json')

# Path to ChromeOS testing key in CrOS checkout.
CROS_TEST_KEYS_DIR = 'src/scripts/mod_for_test_scripts/ssh_keys/'
CROS_TEST_KEY_PRIV = os.path.join(CROS_TEST_KEYS_DIR, 'testing_rsa')
CROS_TEST_KEY_PUB = os.path.join(CROS_TEST_KEYS_DIR, 'testing_rsa.pub')

# Exit code to use on error.
ERROR_EXIT_CODE = 1

# URL base for viewing a job.
JOB_URL_BASE = 'http://cautotest/afe/#tab_id=view_job&object_id='


def KerberosExceptionHandler(f):
  """Decorator which provides additional information for Kerberos exceptions."""

  def _Wrapped():
    try:
      return f()
    except common_util.ChromeOSTestError, e:
      if 'Kerberos' in e[-1]:
        LogErrorAndExit(
            'There appears to be a problem with your credentials. Please run'
            ' kinit and try again.')
      else:
        raise

  return _Wrapped


def FindTest(autotest_dir, test_regex):
  """Uses a test name regex to find the proper control file in Autotest dirs."""
  search_paths = 'client/tests client/site_tests server/tests server/site_tests'
  cmd = ('find %s -maxdepth 2 -type f \\( -name control.* -or -name control \\)'
         '| egrep -v "~$" | egrep "%s"' % (search_paths, test_regex))
  return common_util.RunCommand(cmd=cmd, cwd=autotest_dir, output=True)


def FindAutotestDir(options):
  """Determine whether to use cros_workon or emerged Autotests. Returns path."""
  if options.autotest_dir:
    if not os.path.exists(options.autotest_dir):
      LogErrorAndExit('Could not find the specified Autotest directory.')
    else:
      logging.info('As requested, using the specified Autotest directory '
                   'at %s.', Colors.Color(Colors.BOLD_BLUE,
                                          options.autotest_dir))
    return options.autotest_dir

  autotest_dir = os.path.join(options.cros_dir, DEFAULT_AUTOTEST_DIR)
  if options.use_emerged:
    autotest_dir = os.path.join(
        options.cros_dir, 'chroot/build', options.board, 'usr/local/autotest')
    if not os.path.exists(autotest_dir):
      LogErrorAndExit('Could not find pre-installed autotest, you need to '
                      'emerge-%s autotest autotest-tests.', options.board)
    logging.info('As requested, using emerged autotests already installed at '
                 '%s.', Colors.Color(Colors.BOLD_BLUE, autotest_dir))
  elif not os.path.exists(autotest_dir):
    LogErrorAndExit('Could not find Autotest, run "cros_workon start autotest" '
                    'and "repo sync" to continue.')
  else:
    logging.info('Detected cros_workon autotests. Using autotests from %s. To '
                 'use emerged autotest, pass --use_emerged.',
                 Colors.Color(Colors.BOLD_BLUE, autotest_dir))
  return autotest_dir


def VerifyImageAndGetId(cros_dir, image_path):
  """Verifies image is a test image and returns tuple of version, hash."""
  build_util.MountImage(cros_dir, os.path.dirname(image_path),
                        image_file=os.path.basename(image_path))
  try:
    cmd = 'cat etc/lsb-release | grep CHROMEOS_RELEASE_DESCRIPTION'
    msg = 'Failed to read /etc/lsb-release from mounted image!'
    version = common_util.RunCommand(
        cmd=cmd, cwd=os.path.join(
            os.path.dirname(image_path), build_util.ROOTFS_MOUNT_DIR),
        error_msg=msg, output=True)

    cmd = ('diff root/.ssh/authorized_keys %s'
           % os.path.join(cros_dir, CROS_TEST_KEY_PUB))
    msg = 'The specified image is not a test image! Only test images allowed.'
    common_util.RunCommand(
        cmd=cmd, cwd=os.path.join(
            os.path.dirname(image_path), build_util.ROOTFS_MOUNT_DIR),
        error_msg=msg)
  finally:
    build_util.UnmountImage(cros_dir, os.path.dirname(image_path))

  # String looks like '<tag>=<version> (Test Build <hash> ...' After =, we want
  # the first and third elements. TODO(dalecurtis): verify what we're parsing.
  return version.split('=')[1].split(' ')[0:4:3]


def ProcessLocalBuild(cros_dir, dev, image_path, force=False):
  """Process a local build. Verifies and converts a test image into updates.

  Args:
    cros_dir: Location of Chrome OS code base.
    dev: Instantiated Dev Server Class.
    image_path: Path to test image to verify and convert.
    force: Force creation of updates even if build already exists on server.

  Returns:
    Tuple of (build_tag, image_dir, remote_build_dir).
        build_tag: Unique identifier for this build.
        image_dir: Path on local disk
  """
  logging.info('Verifying the specified image is a test image.')
  build_version, build_hash = VerifyImageAndGetId(cros_dir, image_path)

  build_tag = '%s-%s-%s' % (os.environ['USER'], build_version, build_hash)
  logging.info(
      'Processing build %s.', Colors.Color(Colors.BOLD_BLUE, build_tag))

  if force:
    logging.info('Forcing upload of new build components due to --force.')

  # Prepare the Dev Server for this build.
  remote_build_dir, exists = dev.PrepareDevServer(
      '/'.join([DEV_BUILD_PREFIX, build_tag]), force=force)

  image_dir = os.path.dirname(image_path)
  image_file = os.path.basename(image_path)

  try:
    # Create update zips if they don't exist.
    if not exists:
      logging.info('Generating update.')
      build_util.CreateUpdateZip(
          cros_dir, image_dir, image_file=image_file)

      # Create stateful update zip.
      logging.info('Generating stateful update.')
      build_util.CreateStatefulZip(cros_dir, image_dir, image_file=image_file)
    else:
      logging.info(Colors.Color(
          Colors.BOLD_BLUE, 'Using existing build found on Dev Server.'))
  except:
    if remote_build_dir:
      dev.RemoteCommand('rmdir ' + remote_build_dir)
    raise

  return build_tag, image_dir, remote_build_dir, exists


def LogErrorAndExit(msg, *args, **kwargs):
  """Simple log error and exit method."""
  logging.error(Colors.Color(Colors.BOLD_RED, msg), *args, **kwargs)
  sys.exit(ERROR_EXIT_CODE)


@KerberosExceptionHandler
def GetPlatformList():
  """Return a list of Autotest platform labels accessible to current user."""
  platform_list = autotest_util.GetPlatformList()
  if not platform_list:
    LogErrorAndExit('There are no platforms ACL accessible by you. Please'
                    ' contact the ChromeOS Autotest team'
                    ' (chromeos-autotest@google.com).')
  return platform_list


@KerberosExceptionHandler
def PrintMachineList():
  """Display the output of atest host list."""
  cmd = '%s host list --user $USER' % autotest_util.ATEST_PATH
  msg = 'Failed to retrieve host list from Autotest.'
  print common_util.RunCommand(cmd, error_msg=msg, output=True)


def ParseOptions():
  """Parse and verify command line options.

  Returns:
    Tuple of options dictionary, relative path to test control file, the path to
    Autotest, and the lab test JSON config.
  """
  parser = optparse.OptionParser(
      'usage: %prog [options] <test name>\n'
      '\n'
      'The test name can be a regular expression so long as it only'
      ' matches a single test. For example:\n'
      '\n'
      '  %prog -i test.bin --board x86-generic BootPerfServer')

  parser.add_option('--autotest_dir', help='Skip autodetection of autotest and '
                    'use the specified location.')
  parser.add_option('--board', dest='board',
                    help=('The board for which you are building autotest. Will '
                          'attempt to read default from <cros_dir>/%s'
                          % DEFAULT_BOARD_FILE))
  parser.add_option('--build', dest='build',
                    help=('Instead of using a local build, use an official '
                          'build already on the server; e.g. 0.13.507.0 or '
                          'latest to use the most recent build.'))
  parser.add_option('-c', '--cros', dest='cros_dir',
                    default=chromeos_test_common.CROS_DIR,
                    help=('Location of Chrome OS code base. Defaults to '
                          '"%default".'))
  parser.add_option('-d', '--debug', dest='debug', action='store_true',
                    default=False, help='Enable debugging output.')
  parser.add_option('-f', '--force', dest='force', action='store_true',
                    default=False,
                    help='Force upload even if build already exists on server.')
  parser.add_option('-i', '--image', dest='image_path',
                    help=('Path to test image to deploy for testing. If no'
                          ' image is specified, the script attempts to use'
                          ' <cros_dir>/%s/<board>/latest/%s'
                          % (DEFAULT_IMAGE_DIR, build_util.TEST_IMAGE)))
  parser.add_option('--list_machines', dest='list_machines',
                    action='store_true',
                    help=('Display the list of available machines as well as'
                          ' their current status.'))
  parser.add_option('-l', '--list_platforms', dest='list_platforms',
                    action='store_true',
                    help=('Display the list of valid platforms for use with'
                          ' --platforms.'))
  parser.add_option('-m', '--mail', dest='mail',
                    help=('A comma seperated list of email addresses to notify'
                          ' upon job completion.'))
  parser.add_option('-o', '--override', dest='override', action='store_false',
                    default=False,
                    help=('Override board and platform safety checks.'
                          ' Experienced users only! Please don\'t brick our'
                          ' machines :)'))
  parser.add_option('-p', '--platforms', dest='platforms',
                    help=('Comma separated list of platforms to use for'
                          ' testing. Use the --list_platforms option to see the'
                          ' list of valid platforms. Multiple tests on the same'
                          ' platform can be run by using the * character; e.g.,'
                          ' 2*<platform> would use two machines of type'
                          ' <platform>.'))
  parser.add_option('-t', '--tests', dest='tests', action='store_true',
                    default=False,
                    help=('Package tests with stateful partition. Will cause'
                          ' the stateful partition to be reuploaded to the'
                          ' server even if it already exists. If tests aren\'t'
                          ' packaged, the versions on the Autotest server will'
                          ' be used.'))
  parser.add_option('--use_emerged', dest='use_emerged', action='store_true',
                    default=False,
                    help='Force use of emerged autotest packages')
  options, args = parser.parse_args()

  if options.debug:
    logging.getLogger().setLevel(logging.DEBUG)

  # Make sure we're outside the chroot.
  if os.path.isfile('/etc/debian_chroot'):
    LogErrorAndExit(
        'LabTest must be run outside the chroot to access corp resources.')

  # Make sure we have prodaccess.
  try:
    common_util.RunCommand(cmd='prodcertstatus')
  except common_util.ChromeOSTestError:
    LogErrorAndExit('LabTest needs production access. Please run prodaccess.')

  if options.list_machines:
    parser.print_help()
    print Colors.Color(
        Colors.BOLD_BLUE,
        '\nGenerating list of machines (this may take a few seconds):')
    PrintMachineList()
    sys.exit(0)

  if options.list_platforms:
    parser.print_help()
    print Colors.Color(
        Colors.BOLD_BLUE,
        '\nGenerating list of valid platforms (this may take a few seconds):')
    for platform in GetPlatformList():
      print '  %s' % platform
    sys.exit(0)

  logging.info('Verifying command line options.')

  if not args:
    LogErrorAndExit('A test name must be specified.')

  # Make sure CrOS checkout directory exists.
  if not os.path.exists(options.cros_dir):
    LogErrorAndExit('Could not find Chrome OS checkout, please specify the path'
                    ' with -c.')

  # Convert paths to abs path.
  for item in ('autotest_dir', 'cros_dir', 'image_path'):
    if getattr(options, item):
      abs_path = os.path.normpath(os.path.join(os.getcwd(),
                                               getattr(options, item)))
      setattr(options, item, abs_path)

  # Attempt to load LabTest config.
  with open(LAB_TEST_CONFIG) as config_file:
    config = json.load(config_file)

  # Attempt to determine the default board.
  default_board_file = os.path.join(options.cros_dir, DEFAULT_BOARD_FILE)
  if not options.board:
    logging.info('No board specified, attempting to load the default.')
    if not os.path.isfile(default_board_file):
      LogErrorAndExit('The default board could not be read. Please specify the '
                      'board type with --board.')
    with open(default_board_file, 'r') as f:
      options.board = f.read().strip()
    logging.info('Using default board "%s"',
                 Colors.Color(Colors.BOLD_BLUE, options.board))

  # Convert boards with multiple names into a single format.
  if options.board in config['preferred_board_fixups']:
    options.board = config['preferred_board_fixups'][options.board]

  if not options.platforms:
    if options.board in config['board_platform_map']:
      # If the platform exists in the map, override any further checks.
      options.override = True
      options.platforms = config['board_platform_map'][options.board]
      logging.info(
          'No platform specified, using the default platform for this board '
          '"%s"', Colors.Color(Colors.BOLD_BLUE, options.platforms))
    else:
      LogErrorAndExit(
          'An unknown board has been specified, please specify the platform '
          'type with --platform.')

  # Make sure the specified image actually exists...
  if options.image_path:
    if not os.path.isfile(options.image_path):
      LogErrorAndExit('The specified test image does not exist.')
  elif not options.build:
    logging.info('No image specified, attempting to find the latest image.')
    options.image_path = os.path.join(
        options.cros_dir, DEFAULT_IMAGE_DIR, options.board, 'latest',
        build_util.TEST_IMAGE)
    if not os.path.isfile(options.image_path):
      LogErrorAndExit(
          'No test image specified and the default could not be found.')
    logging.info(
        'Default image found, using %s',
        Colors.Color(Colors.BOLD_BLUE, options.image_path))

  # Figure out the Autotest directory based on command line options.
  autotest_dir = FindAutotestDir(options)

  # Identify the desired test case. Limit to only one test for now.
  test_pattern = ' '.join(args)
  try:
    matched_test = FindTest(autotest_dir, test_pattern).strip()
  except common_util.ChromeOSTestError:
    LogErrorAndExit('Cannot find a match for test name "%s"' % test_pattern)

  if len(matched_test.split('\n')) > 1:
    logging.error('The given test pattern is ambiguous. Disambiguate by '
                  'passing one of these patterns instead:')
    for test in matched_test.split('\n'):
      logging.error('    ^%s$', test)
    sys.exit(ERROR_EXIT_CODE)

  # Verify the requested platforms.
  platform_list = GetPlatformList()

  # Strip out any multipliers from the platform list.
  platform_split = options.platforms.split(',')
  platform_names = set(p.lstrip('0123456789* ') for p in platform_split)
  bad_platforms = platform_names - set(platform_list)
  if bad_platforms:
    LogErrorAndExit('The following platforms are invalid: %s',
                    ', '.join(bad_platforms))

  # Add 1* for any platforms without a count.
  for i in xrange(0, len(platform_split)):
    if not platform_split[i][0].isdigit():
      platform_split[i] = '1*' + platform_split[i]
  options.platforms = ','.join(platform_split)

  # Verify specified platforms match the provided board.
  if not options.override and options.board != 'x86-generic':
    # Only allow board, platform pairs we have configured for testing.
    cros_config = test_config.TestConfig(
        os.path.join(chromeos_test_common.CRON_DIR,
                     test_config.DEFAULT_CONFIG_FILE))
    valid_platforms = cros_config.ParseConfigGroups(board_re=options.board)[2]

    for p in platform_names:
      if not p in valid_platforms:
        LogErrorAndExit('The specified platform (%s) is not valid for the '
                        'specified board (%s). Valid platforms for this board '
                        'are: %s.', p, options.board,
                        ', '.join(valid_platforms))

  return options, matched_test, autotest_dir, config


def main():
  # Setup logging.
  logging.basicConfig(format='  - %(levelname)s: %(message)s')
  logging.getLogger().setLevel(logging.INFO)

  print '-' * 80
  print ('LabTest! A script to run Autotest jobs on machines in a remote lab.'
         ' (%s)' % __version__)
  print '-' * 80

  options = local_build_dir = remote_build_dir = None
  try:
    # Parse options and find the requested control file.
    options, control_file, autotest_dir, config = ParseOptions()

    logging.info('Running %s on the following platforms: %s',
                 Colors.Color(Colors.BOLD_GREEN, control_file),
                 Colors.Color(Colors.BOLD_GREEN, options.platforms))

    # Load Dev Server configuration.
    dev_config = config['dev_server']

    remote_host = dev_config.get('remote_host', None)

    # Initialize Dev Server.
    dev = DevServer(
        dev_config['dev_host'], dev_config['dir'], dev_config['user'],
        private_key=os.path.join(options.cros_dir, CROS_TEST_KEY_PRIV),
        remote_host=remote_host)

    # Determine if we have any tests to upload. Nothing to upload for suites.
    tests_to_upload = options.tests and not 'suite' in control_file.lower()

    # If the user hasn't specified an official build, process their local build.
    if not options.build:
      build_tag, local_build_dir, remote_build_dir, exists = ProcessLocalBuild(
          options.cros_dir, dev, options.image_path, force=options.force)
    else:
      # Scan the Dev Server for using the partial board, build information we
      # have. Afterward, update the options values with the full ids.
      options.board, options.build = dev.FindDevServerBuild(
          options.board, options.build)
      build_tag = '%s-%s' % (os.environ['USER'], options.build)

      logging.info(
          'Official build requested, using build %s for testing.',
          Colors.Color(Colors.BOLD_GREEN, options.build))

      if tests_to_upload:
        # Create a temporary directory to hold Autotest packages.
        local_build_dir = tempfile.mkdtemp()

        # Make a copy of the official build so we don't corrupt it.
        remote_build_dir = dev.CloneDevServerBuild(
            options.board, options.build,
            '/'.join([DEV_BUILD_PREFIX, build_tag]), force=options.force)

    # Extract test name from path and prepare Autotest packages for upload.
    test_name = os.path.basename(os.path.dirname(control_file))
    if tests_to_upload:
      logging.info('Preparing Autotest packages for upload to Dev Server.')
      build_util.PrepareAutotestPkgs(
          autotest_dir, local_build_dir, test_name=test_name)

    # If we've processed a build, upload all build components.
    if remote_build_dir and not options.build and not exists:
      logging.info('Uploading build components to Dev Server.')
      dev.UploadBuildComponents(remote_build_dir, local_build_dir)
    elif tests_to_upload:
      # Otherwise, just upload Autotest packages if there are any.
      logging.info('Uploading Autotest packages to Dev Server.')
      dev.UploadAutotestPackages(remote_build_dir, local_build_dir)

    # If official build and no modified tests, use an existing build URL.
    if options.build and not tests_to_upload:
      update_url = dev.GetUpdateUrl(options.board, options.build)
    else:
      # Otherwise determine the update URL for the processed build.
      update_url = dev.GetUpdateUrl(DEV_BUILD_PREFIX, build_tag)

    # Hackish, but the only way we have to determine server versus client jobs.
    server = control_file.startswith('server/')

    # Special case to fix up job names in the suites directory. These files are
    # all of the format suites/control.<name>.
    if test_name.lower() == 'suites':
      test_name = os.path.basename(control_file).split('.')[-1]

    # Now that all components are uploaded, start the Autotest job.
    job_name = '%s_%s' % (build_tag, test_name)
    logging.info('Creating job %s.', Colors.Color(Colors.BOLD_BLUE, job_name))
    job_id = autotest_util.CreateJob(
        name=job_name, control=os.path.join(autotest_dir, control_file),
        platforms=options.platforms, update_url=update_url, server=server,
        mail=options.mail)

    logging.info(
        Colors.Color(Colors.BOLD_GREEN, 'Job created successfully, URL: %s%s'),
        JOB_URL_BASE, job_id)
  except Exception, e:
    if remote_build_dir:
      dev.RemoteCommand('rm -rf ' + remote_build_dir)

    if isinstance(e, common_util.ChromeOSTestError):
      logging.error(Colors.Color(Colors.BOLD_RED, e[0]))
      if not options or options.debug:
        logging.exception(e)
    else:
      raise
  finally:
    # When --build is used, local_build_dir contains only tmp files, so cleanup.
    if options and options.build and local_build_dir:
      common_util.RunCommand('rm -rf ' + local_build_dir)


if __name__ == '__main__':
  main()
