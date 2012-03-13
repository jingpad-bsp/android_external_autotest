# Copyright (c) 2012 The Chromium OS Authors. All rights reserved.
# Use of this source code is governed by a BSD-style license that can be
# found in the LICENSE file.

"""A common Autotest utility library used by other Chrome OS scripts.

Various helper functions for finding hosts, creating control files, and creating
Autotest jobs.
"""

__author__ = 'dalecurtis@google.com (Dale Curtis)'

import getpass
import logging
import optparse
import os
import posixpath
import re

import common_util


# Pre-built Autotest location. Does not contain [client/server]/site_tests.
if 'chromeos-test' == getpass.getuser():
  # The Autotest user should use the local install directly.
  AUTOTEST_BIN_DIR = os.path.abspath(os.path.join(
          os.path.dirname(__file__), '..', '..'))
else:
  # All regular users need to use this for now.
  # Until we can drop SSO this is required.
  AUTOTEST_BIN_DIR = '/home/chromeos-test/autotest'

# Path to atest executable.
ATEST_PATH = os.path.join(AUTOTEST_BIN_DIR, 'cli/atest')

# Maximum retries for test importer failures (rsync or site_test_importer.sh).
MAX_IMPORT_RETRY = 3

# Amount of time to sleep (in seconds) between import command retries.
RETRY_SLEEP_SECS = 5

# Directories to be rsync'd to remote server from extracted autotest tarball.
SYNC_DIRS = ['autotest/server', 'autotest/client']


def CreateJob(name, control, platforms, labels=None, server=True,
              sync=None, update_url=None, cli=ATEST_PATH, mail=None,
              priority='medium'):
  """Creates an Autotest job using the provided parameters.

  Uses the atest CLI tool to create a job for the given hosts with the given
  parameters.

  Args:
    name: Name of job to create.
    control: Path to Autotest control file to use.
    platforms: Platform labels to schedule job for.
    labels: Only use hosts with these labels. Can be a list or a comma delimited
     str.
    server: Run the job as a server job? Defaults to true.
    sync: Number of hosts to process synchronously.
    update_url: Dev Server update URL each host should pull update from.
    cli: Path to atest (Autotest CLI) to use for this job.
    mail: Comma separated list of email addresses to notify upon job completion.
    priority: The job priority (low, medium, high, urgent), default medium.

  Returns:
    Job id if successful.

  Raises:
    common_util.ChromeOSTestError: If Autotest job can't be created.
  """
  cmd_list = [cli, 'job create', '--machine ' + platforms,
              '--control-file ' + control]

  if server:
    cmd_list.append('--server')
  if sync:
    cmd_list.append('--synch_count %d' % sync)
  if update_url:
    cmd_list.append('--image ' + update_url)
  if mail:
    cmd_list.append('--email ' + mail)
  if priority:
    cmd_list.append('--priority %s' % priority.lower())

  if labels:
    if isinstance(labels, list):
      # Convert labels to comma separated list and escape labels w/ commas.
      # if we were given a list.
      labels = ','.join([label.replace(',', r'\\,') for label in labels])
    cmd_list.append('--dependencies ' + labels)

  cmd_list.append(name)
  msg = 'Failed to create Autotest job %s !' % name
  output = common_util.RunCommand(
      cmd=' '.join(cmd_list), error_msg=msg, output=True)
  return re.sub(r'[^\d-]+', '', (output.split('id')[1].strip()))


def ImportTests(hosts, staging_dir):
  """Distributes tests to a list of hosts and runs site_test_importer.

  Given a list of hosts, rsync the contents of SYNC_DIRS from the Autotest
  tarball to the remote directory specified. The following script will be called
  on each host until one of them completes successfully.

      <dir>/utils>/site_test_importer.sh

  Method assumes password-less login has been setup for the hosts.

  Args:
    hosts: List of Autotest hosts containing host, user, and path; e.g.,
        [{'host': '127.0.0.1', 'user': 'user', 'path': '/usr/local/autotest'},
         {'host': '127.0.0.2', 'user': 'user', 'path': '/usr/local/autotest'}}
    staging_dir: Directory containing extracted autotest.tar.bz2

  Returns:
    True if all hosts synced successfully. False otherwise.
  """
  all_ok = True
  imported_tests = False
  for host in hosts:
    try:
      # Copy relevant files and directories, keep permissions on remote host.
      for sdir in SYNC_DIRS:
        cmd = 'rsync -a --safe-links --no-p %s %s@%s:%s' % (
            sdir, host['user'], host['host'], host['path'])
        msg = 'Failed to rsync %s to %s@%s:%s' % (
            sdir, host['user'], host['host'], host['path'])
        common_util.RunCommand(cmd, cwd=staging_dir, error_msg=msg,
                               retries=MAX_IMPORT_RETRY,
                               retry_sleep=RETRY_SLEEP_SECS)

      # Run test importer.
      if not imported_tests:
        cmd = 'ssh %s@%s %s' % (host['user'], host['host'],
                                posixpath.join(host['path'],
                                               'utils/site_test_importer.sh'))
        msg = 'Failed to run site_test_importer.sh on %s@%s!' % (
            host['user'], host['host'])
        common_util.RunCommand(cmd, error_msg=msg, retries=MAX_IMPORT_RETRY,
                               retry_sleep=RETRY_SLEEP_SECS)
        imported_tests = True
    except common_util.ChromeOSTestError, e:
      logging.exception(e)
      all_ok = False

  return all_ok


def GetPlatformDict(cli=ATEST_PATH):
  """Returns a dict of platforms + labels usable by the current user.

  @returns a dict with platform as a key and value of a set representing labels
  associated with a given platform.
  """

  cmd = '%s host list --parse --user $USER' % cli
  msg = 'Failed to retrieve host list from Autotest.'
  output = common_util.RunCommand(cmd=cmd, error_msg=msg, output=True)

  # atest host list will return a tabular data set with columns separated by |
  # characters. From each line we only want the platform label.
  platform_dict = {}
  if output:
    for line in output.splitlines():
      temp_dict = {}
      for entry in line.split('|'):
        key, values = entry.split('=', 1)
        temp_dict[key.strip()] = values.strip()
      platform = temp_dict.get('Platform', None)
      if not platform:
        continue
      labels = temp_dict.get('Labels', '').split()
      for label in labels:
        if label.startswith('rps') or label.startswith('cros'):
          continue
        platform_dict.setdefault(platform, set()).add(label)

  return platform_dict


def GetHostList(cli=ATEST_PATH, acl=None, label=None, user=None, status=None):
  """Returns a list containing hosts retrieved from the atest CLI.

  Args:
    cli: path to atest.
    acl: acl to use in atest query.
    label: label to use in atest query.
    user: user to use in atest query.
    status: status to use in atest query.

  Returns:
    A list of host names.

  Raises:
    common_util.ChromeOSTestError: If host list can't be retrieved.
  """
  return [host for host in GetHostData(cli, acl, label, user, status)]


def GetHostData(cli=ATEST_PATH, acl=None, label=None, user=None, status=None):
  """Returns a dict containing full host info retrieved from the atest CLI.

  Args:
    cli: path to atest.
    acl: acl to use in atest query.
    label: label to use in atest query.
    user: user to use in atest query.
    status: status to use in atest query.

  Returns:
    A dict of host data.

  Raises:
    common_util.ChromeOSTestError: If host data can't be retrieved.
  """
  afe_hosts = {}

  cmd = [cli, 'host list']
  if acl:
    cmd += ['-a', acl]
  if label:
    cmd += ['-b', label]
  if user:
    cmd += ['-u', user]
  if status:
    cmd += ['-s', status]
  cmd_str = ' '.join(cmd)

  msg = 'Failed to retrieve hosts data from autotest.'
  atest_out = common_util.RunCommand(cmd=cmd_str, error_msg=msg, output=True)
  if not atest_out:
    return afe_hosts

  lines = atest_out.splitlines()[1:]
  for line in lines:
    # The only two word status is 'Repair Failed'. In that case insert a '_'
    # to make a single word status 'Repair_Failed'.
    fields = line.replace('Repair Failed', 'Repair_Failed').split()
    if len(fields) > 3:
      afe_hosts[fields[0]] = {
          'status': fields[1],
          'locked': fields[2],
          'platform': fields[3],
          'labels': []}
      if len(fields) > 4:
        afe_hosts[fields[0]]['labels'] = fields[4:]

  return afe_hosts


def AddOptions(parser, cli_only=False):
  """Add command line option group for atest usage.

  Optional method to add helpful command line options to calling programs.
  Adds Options:
    --cli: Location of atest
    --acl: acl to use in atest query
    --label: label to use in atest query
    --status: status to use in atest query
    --user: user to use in atest query

  Args:
    parser: OptionParser to add autotest flags to.
    cli_only: When true only add the --cli flag to argument list.

  Returns:
    OptionGroup: Users can add additional options to the returned group.
  """
  group = optparse.OptionGroup(parser,
                               title='Autotest CLI Configuration',
                               description=('Options specifying the location'
                                            ' and arguments to Atest.'))
  group.add_option('--cli',
                   help='Autotest CLI executable location [default: %default]',
                   default=ATEST_PATH)
  if not cli_only:
    group.add_option('--acl',
                     help=('Autotest ACL Group to query for host machines. '
                           'http://cautotest/afe/server/admin/afe/aclgroup/'
                           ' [default: %default]'),
                     default='acl_cros_test')
    group.add_option('--label',
                     help=('Only run on hosts with the specified label. '
                           'Examples: board_x86-generic, has_80211n, has_ssd. '
                           'See http://cautotest/afe/server/admin/afe/label/'))
    group.add_option('--status',
                     help=('Only run on hosts with the specified status. '
                           'Examples: Running, Ready, Repair.'))
    group.add_option('--user',
                     help='Only run on hosts with the specified user.')
  return parser.add_option_group(group)
