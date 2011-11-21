# Copyright (c) 2011 The Chromium OS Authors. All rights reserved.
# Use of this source code is governed by a BSD-style license that can be
# found in the LICENSE file.

"""A common function library used by other Chrome OS scripts.

Various helper functions for running commands and handling exceptions.
"""

__author__ = 'dalecurtis@google.com (Dale Curtis)'

import errno
import logging
import os
import subprocess
import sys
import tempfile
import time


_SSH_OPTIONS = ('-o StrictHostKeyChecking=no -o UserKnownHostsFile=/dev/null'
                ' -o ConnectTimeout=30')


class ChromeOSTestError(Exception):
  """Generic error for ChromeOS Test exceptions."""


def RunCommand(cmd, cwd=None, env=None, error_msg=None, output=False,
               retries=0, retry_sleep=0, ignore_errors=False, error_file=False):
  """Executes a command with the given environment and working directory.

  Unless output is set to True, all output (stdout, stderr) is suppressed. The
  command success is determined by an exit code of zero.

  Args:
    cmd: Command to execute.
    cwd: Set current working directory.
    env: Dictionary of environment variables to pass to subprocess.Popen. Merged
        on top of os.environ.
    error_msg: Message used when raising an exception after command failure.
    output: Should output be kept? If used with error_file, output file name is
        returned on completion.
    retries: Number of times to retry a command before raising an exception.
    retry_sleep: Amount of time to sleep between retries.
    ignore_errors: Don't raise an exception on error.
    error_file: Store output to a file. On failure include file name in
        exception, otherwise the file is deleted if command is successful (
        unless ouput is True). Multiple retries are written to the same file.

  Returns:
    If output is True and error_file is False, the contents of stdout will be
    returned upon command success. Returns None if there is no output (after
    passing through strip()).

    If output is True and error_file is True, the output file name will be
    returned upon command success.

  Raises:
    ChromeOSTestError: If command fails. Message is set by the error_msg
        parameter.
  """
  logging.debug('Running command "%s"', cmd)

  # Import environment variables from os so we have proper PATH, etc.
  if env is not None:
    local_env = os.environ.copy()
    local_env.update(env)
    env = local_env

  # Setup output pipes depending on if output was requested. Use a /dev/null
  # file handle to save on having to store output.
  if error_file:
    pipe, temp_fn = tempfile.mkstemp(
        prefix=os.path.basename(sys.argv[0]).split('.')[0], suffix='.log')
  elif output:
    pipe = subprocess.PIPE
  else:
    pipe = os.open(os.devnull, os.O_WRONLY)

  for retry in xrange(0, retries + 1):
    # Use Popen instead of call so we don't deadlock on massive amounts of
    # output (like the autotest image import...).
    p = subprocess.Popen(cmd, env=env, cwd=cwd, shell=True, stdout=pipe,
                         stderr=pipe)

    # Used instead of p.wait() to prevent deadlock. See subprocess man page.
    stdout, stderr = p.communicate()

    if p.returncode == 0:
      break

    if retry < retries:
      logging.warning('%s [Retrying; attempt #%d]', error_msg, retry + 1)
      time.sleep(retry_sleep)

  if pipe != subprocess.PIPE:
    os.close(pipe)

  if stdout:
    stdout = stdout.strip()

  if p.returncode != 0 and not ignore_errors:
    if error_file:
      raise ChromeOSTestError(error_msg,
                              'Command: %s' % cmd,
                              'Exit code: %s' % p.returncode,
                              'Output file: %s' % temp_fn)
    elif output:
      raise ChromeOSTestError(error_msg,
                              'Command: %s' % cmd,
                              'Exit code: %s' % p.returncode,
                              'Output: %s' % stdout, 'Error: %s' % stderr)
    else:
      raise ChromeOSTestError(error_msg, 'Command: %s' % cmd,
                              'Exit code: %s' % p.returncode)
  elif output and error_file:
    return temp_fn
  elif output:
    return stdout
  elif error_file:
    os.unlink(temp_fn)


def MakedirsExisting(path, mode=None):
  """Wrapper method for os.makedirs to provide mkdir -p functionality.

  Args:
    path: Local directory to create.
    mode: Numeric mode to set path to, e.g., 0755 for world readable.
  """
  try:
    os.makedirs(path)
  except OSError, e:
    if e.errno == errno.EEXIST:
      pass
    else:
      raise
  if mode is not None:
    os.chmod(path, mode)


def _MakeSSHCommand(private_key=None):
  """Helper function for building rsync command line.

  Args:
    private_key: Path to SSH private key for password less ssh login.

  Returns:
    Command line for using SSH.
  """
  ssh_cmd_list = ['ssh', _SSH_OPTIONS, '-o', 'Compression=no']
  if private_key:
    ssh_cmd_list.append('-i')
    ssh_cmd_list.append(private_key)
  return ' '.join(ssh_cmd_list)


def _MakeRSyncCommand(private_key=None):
  """Helper function for building rsync command line.

  Args:
    private_key: Path to SSH private key for password less ssh login.

  Returns:
    Command line for using rsync.
  """
  return ' '.join(['rsync', '-az', '-e', '"%s"' % _MakeSSHCommand(private_key)])


def RemoteCommand(remote_host, remote_user, cmd, private_key=None, **kwargs):
  """Wrapper function for RunCommand to execute commands via SSH.

  Takes the cmd argument and prepends "ssh <user>@<ip> ". See definition for
  RunCommand for complete argument definitions.

  Args:
    remote_host: Name of the remote host.
    remote_user: User name used to ssh into the remote host.
    cmd: Command to execute on remote host.
    private_key: Path to SSH private key for password less ssh login.

  Returns:
    Results from RunCommand()
  """
  return RunCommand(
      '%s %s@%s "%s"' % (
          _MakeSSHCommand(private_key), remote_user, remote_host, cmd),
      **kwargs)


def RemoteCopy(remote_host, remote_user, src, dest, private_key=None, **kwargs):
  """Wrapper function for RunCommand to copy files via rsync.

  Takes a source and remote destination and uses rsync to copy the files. See
  definition for common_util.RunCommand for complete argument definitions.

  Args:
    remote_host: Name of the remote host.
    remote_user: User name used to ssh into the remote host.
    src: Local path/file to pass into rsync.
    dest: Remote destination on Dev Server.
    private_key: Path to SSH private key for password less ssh login.

  Returns:
    Results from RunCommand()
  """
  return RunCommand(
      '%s %s %s@%s:%s' % (
          _MakeRSyncCommand(private_key), src, remote_user, remote_host, dest),
      **kwargs)
