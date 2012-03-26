# Copyright (c) 2012 The Chromium OS Authors. All rights reserved.
# Use of this source code is governed by a BSD-style license that can be
# found in the LICENSE file.

"""Helper class for interacting with the Dev Server.

DevServer is the controlling class for all Dev Server interactions. All Dev
Server centric methods are collected here.

Using the locking methods provided in this class, multiple instances of various
tools and methods can be run concurrently with guaranteed safety.
"""

__author__ = 'dalecurtis@google.com (Dale Curtis)'

import logging
import os
import posixpath

# Autotest imports
import common
from autotest_lib.client.common_lib.cros import dev_server

import common_util


class DevServer(object):
  """Helper class for interacting with the Dev Server.

  All methods assume password-less login for the Dev Server has been set up or
  methods are being run interactively.
  """
  AU_BASE = 'au'
  LATEST = 'LATEST'
  ROOT_UPDATE = 'update.gz'
  STATEFUL_UPDATE = 'stateful.tgz'
  TEST_IMAGE = 'chromiumos_test_image.bin'

  def __init__(self, dev_host, path, user, private_key=None, remote_host=None):
    """Initializes class variables and fixes private key permissions.

    Args:
      host: Address of the Dev Server.
      path: Images directory root on Dev Server.
      user: Dev Server SSH user name.
      private_key: Optional private key file for password-less login. If the
          key file has any group or world permissions they will be removed.
      remote_host: If a different hostname/ip should be needed for uploading
          images to the dev server.
    """
    self._dev_host = dev_host
    if remote_host:
      self._remote_host = remote_host
    else:
      self._remote_host = dev_host
    self._user = user
    self._images = path
    self._private_key = private_key
    if self._private_key:
      # Check that there are no group or world permissions.
      perms = os.stat(self._private_key).st_mode
      if perms & 0o77 != 0:
        # Remove group and world permissions, keep higher order bits.
        os.chmod(self._private_key, (perms >> 6) << 6)
        logging.warning(
            'Removing group and world permissions from private key %s to make'
            ' SSH happy.', self._private_key)

  def GetLatestBuildVersion(self, board):
    """Retrieves the latest build version from Dev Server for a given board.

    Sends a request to http://devserver/latestbuild?target=x86-mario-release to
    find the latest build for a given target.

    Args:
      board: Board name for this build; e.g., x86-generic-rel

    Returns:
      The returned string from the devserver.

    Raises:
      common_util.ChromeOSTestError: If the build version can't be retrieved.
    """
    new_dev_server = dev_server.DevServer()
    latest_build = new_dev_server.get_latest_build(board)
    if not latest_build:
      # Raise this to keep the previously established API.
      raise common_util.ChromeOSTestError(
          'Unable to determine the latest build for %s' % board)

    return latest_build

  def UploadAutotestPackages(self, remote_dir, staging_dir):
    """Uploads Autotest packages from staging directory to Dev Server.

    Specifically, the autotest-pkgs directory is uploaded from the staging
    directory to the specified Dev Server.

    Args:
      remote_dir: Directory to upload build components into.
      staging_dir: Directory containing update.gz and stateful.tgz

    Raises:
      common_util.ChromeOSTestError: If any steps in the process fail to
          complete.
    """
    if os.path.isdir(os.path.join(staging_dir, 'autotest-pkgs')):
      # Upload autotest-pkgs to Dev Server.
      remote_pkgs_dir = posixpath.join(remote_dir, 'autotest')
      msg = 'Failed to upload autotest packages to Dev Server!'
      self.RemoteCopy(src='autotest-pkgs/*', dest=remote_pkgs_dir,
                      cwd=staging_dir, error_msg=msg)

  def UploadBuildComponents(self, remote_dir, staging_dir, upload_image=False):
    """Uploads various build components from staging directory to Dev Server.

    Specifically, the following components are uploaded:
      - update.gz
      - stateful.tgz
      - chromiumos_test_image.bin
      - The entire contents of the au directory. Symlinks are generated for each
        au payload as well.
      - Contents of autotest-pkgs directory.
      - Control files from autotest/server/{tests, site_tests}

    Args:
      remote_dir: Directory to upload build components into.
      staging_dir: Directory containing update.gz and stateful.tgz
      upload_image: Should the chromiumos_test_image.bin be uploaded?

    Raises:
      common_util.ChromeOSTestError: If any steps in the process fail to
          complete.
    """
    upload_list = [self.ROOT_UPDATE, self.STATEFUL_UPDATE]
    if upload_image:
      upload_list.append(self.TEST_IMAGE)
    else:
      # Create blank chromiumos_test_image.bin. Otherwise the Dev Server will
      # try to rebuild it unnecessarily.
      cmd = 'touch ' + posixpath.join(remote_dir, self.TEST_IMAGE)
      msg = 'Failed to create %s on Dev Server!' % self.TEST_IMAGE
      self.RemoteCommand(cmd, error_msg=msg)

    # Upload AU payloads.
    au_path = os.path.join(staging_dir, self.AU_BASE)
    if os.path.isdir(au_path):
      upload_list.append(self.AU_BASE)

      # For each AU payload, setup symlinks to the main payloads.
      cwd = os.getcwd()
      for au in os.listdir(au_path):
        os.chdir(os.path.join(staging_dir, au_path, au))
        os.symlink('../../%s' % self.TEST_IMAGE, self.TEST_IMAGE)
        os.symlink('../../%s' % self.STATEFUL_UPDATE, self.STATEFUL_UPDATE)
        os.chdir(cwd)

    msg = 'Failed to upload build components to the Dev Server!'
    self.RemoteCopy(
        ' '.join(upload_list), dest=remote_dir, cwd=staging_dir, error_msg=msg)

    self.UploadAutotestPackages(remote_dir, staging_dir)

    if os.path.isdir(os.path.join(staging_dir, 'autotest')):
      remote_server_dir = posixpath.join(remote_dir, 'server')
      cmd = 'mkdir -p ' + remote_server_dir
      msg = 'Failed to create autotest server dir on Dev Server!'
      self.RemoteCommand(cmd, error_msg=msg)

      # Upload autotest/server/{tests,site_tests} onto Dev Server.
      msg = 'Failed to upload autotest/server/{tests,site_tests} to Dev Server!'
      self.RemoteCopy(src='autotest/server/{tests,site_tests}',
                      dest=remote_server_dir, cwd=staging_dir, error_msg=msg)

  def AcquireLock(self, tag):
    """Acquires a Dev Server lock for a given tag.

    Creates a directory for the specified tag on the Dev Server, telling other
    components the resource/task represented by the tag is unavailable.

    Args:
      tag: Unique resource/task identifier. Use '/' for nested tags.

    Returns:
      Path to the created directory on Dev Server or None if creation failed.

    Raises:
      common_util.ChromeOSTestError: If Dev Server lock can't be acquired.
    """
    remote_dir = posixpath.join(self._images, tag)

    # Attempt to make the directory '<image dir>/<tag>' on the Dev Server. Doing
    # so tells other components that this build is being/was processed by
    # another instance. Directory creation is atomic and will return a non-zero
    # exit code if the directory already exists.
    cmd = 'mkdir ' + remote_dir
    self.RemoteCommand(cmd)
    return remote_dir

  def ReleaseLock(self, tag):
    """Releases Dev Server lock for a given tag. Removes lock directory content.

    Used to release an acquired Dev Server lock. If lock directory is not empty
    the lock will fail to release.

    Args:
      tag: Unique resource/task identifier. Use '/' for nested tags.

    Raises:
      common_util.ChromeOSTestError: If processing lock can't be released.
    """
    remote_dir = posixpath.join(self._images, tag)

    cmd = 'rmdir ' + remote_dir
    self.RemoteCommand(cmd)

  def UpdateLatestBuild(self, board, build):
    """Create and upload LATEST file to the Dev Server for the given build.

    If a LATEST file already exists, it's renamed to LATEST.n-1

    Args:
      board: Board name for this build; e.g., x86-generic-rel
      build: Full build string to look for; e.g., 0.8.61.0-r1cf43296-b269
    """
    try:
      latest_path = posixpath.join(self._images, board, self.LATEST)

      # Update the LATEST file and move any existing LATEST to LATEST.n-1. Use
      # cp instead of mv to prevent any race conditions elsewhere.
      cmd = '[ -f "%s" ] && cp "%s" "%s.n-1"; echo %s>"%s"' % (
          latest_path, latest_path, latest_path, build, latest_path)
      self.RemoteCommand(cmd=cmd)
    except common_util.ChromeOSTestError:
      # Log an error, but don't raise an exception. We don't want to blow away
      # all the work we did just because we can't update the LATEST file.
      logging.error('Could not update %s file for board %s, build %s.',
                    self.LATEST, board, build)

  def GetUpdateUrl(self, board, build):
    """Returns Dev Server update URL for use with memento updater.

    Args:
      board: Board name for this build; e.g., x86-generic-rel
      build: Full build string to look for; e.g., 0.8.61.0-r1cf43296-b269

    Returns:
      Properly formatted Dev Server update URL.
    """
    return 'http://%s:8080/update/%s/%s' % (self._dev_host, board, build)

  def FindMatchingBoard(self, board):
    """Returns a list of boards given a partial board name.

    Args:
      board: Partial board name for this build; e.g., x86-generic

    Returns:
      Returns a list of boards given a partial board and build.
    """
    cmd = 'cd %s; ls -d %s*' % (self._images, board)
    output = self.RemoteCommand(cmd, ignore_errors=True, output=True)
    if output:
      return output.splitlines()
    else:
      return []

  def FindMatchingBuild(self, board, build):
    """Returns a list of matching builds given a board and partial build.

    Args:
      board: Partial board name for this build; e.g., x86-generic-rel
      build: Partial build string to look for; e.g., 0.8.61.0

    Returns:
      Returns a list of (board, build) tuples given a partial board and build.
    """
    cmd = 'cd %s; find \$(ls -d %s*) -maxdepth 1 -type d -name "%s*"' % (
        self._images, board, build)
    results = self.RemoteCommand(cmd, output=True)
    if results:
      return [tuple(line.split('/')) for line in results.splitlines()]
    else:
      return []

  def RemoteCommand(self, cmd, **kwargs):
    """Wrapper function for executing commands on the Dev Server.

    Args:
      cmd: Command to execute on Dev Server.

    Returns:
      Results from common_util.RunCommand()
    """
    return common_util.RemoteCommand(self._remote_host, self._user, cmd,
                                     private_key=self._private_key, **kwargs)

  def RemoteCopy(self, src, dest, **kwargs):
    """Wrapper function for copying a file to the Dev Server.

    Copies from a local source to a remote destination (on the Dev Server). See
    definition for common_util.RunCommand for complete argument definitions.

    Args:
      src: Local path/file.
      dest: Remote destination on Dev Server.

    Returns:
      Results from common_util.RemoteCopy()
    """
    return common_util.RemoteCopy(self._remote_host, self._user, src, dest,
                                  private_key=self._private_key, **kwargs)

  def PrepareDevServer(self, tag, force=False):
    """Prepare Dev Server file system to recieve build components.

    Checks if the component directory for the given build is available and if
    not creates it.

    Args:
      tag: Unique resource/task identifier. Use '/' for nested tags.
      force: Force re-creation of remote_build_dir even if it already exists.

    Returns:
      Tuple of (remote_build_dir, exists).
          remote_build_dir: The path on Dev Server to the remote build.
          exists: Indicates whether the directory was already present.
    """
    # Check Dev Server for the build before we begin processing.
    remote_build_dir = posixpath.join(self._images, tag)

    # If force is request, delete the existing remote build directory.
    if force:
      self.RemoteCommand('rm -rf ' + remote_build_dir)

    # Create remote directory. Will fail if it already exists.
    exists = self.RemoteCommand('[ -d %s ] && echo exists || mkdir -p %s' % (
        remote_build_dir, remote_build_dir), output=True) == 'exists'

    return remote_build_dir, exists

  def FindDevServerBuild(self, board, build):
    """Given partial build and board ids, figure out the appropriate build.

    Args:
      board: Partial board name for this build; e.g., x86-generic
      build: Partial build string to look for; e.g., 0.8.61.0 or "latest" to
          return the latest build for for most newest board.

    Returns:
      Tuple of (board, build):
          board: Fully qualified board name; e.g., x86-generic-rel
          build: Fully qualified build string; e.g., 0.8.61.0-r1cf43296-b269

    Raises:
      common_util.ChromeOSTestError: If no boards, no builds, or too many builds
          are matched.
    """
    # Find matching updates on Dev Server.
    if build.lower().strip() == 'latest':
      boards = self.FindMatchingBoard(board)
      if not boards:
        raise common_util.ChromeOSTestError(
            'No boards matching %s could be found on the Dev Server.' % board)

      # Take the last board in sorted order, under the assumption that the last
      # entry will be the most recent board (...-r12, ...-r13, ...).
      board = sorted(boards)[-1]
      build = self.GetLatestBuildVersion(board)
    else:
      builds = self.FindMatchingBuild(board, build)
      if not builds:
        raise common_util.ChromeOSTestError(
            'No builds matching %s could be found for board %s.' % (
                build, board))

      if len(builds) > 1:
        raise common_util.ChromeOSTestError(
            'The given build id is ambiguous. Disambiguate by using one of'
            ' these instead: %s' % ', '.join([b[1] for b in builds]))

      board, build = builds[0]

    return board, build

  def CloneDevServerBuild(self, board, build, tag, force=False):
    """Clone existing Dev Server build. Returns path to cloned build.

    Args:
      board: Fully qualified board name; e.g., x86-generic-rel
      build: Fully qualified build string; e.g., 0.8.61.0-r1cf43296-b269
      tag: Unique resource/task identifier. Use '/' for nested tags.
      force: Force re-creation of remote_build_dir even if it already exists.

    Returns:
      The path on Dev Server to the remote build.
    """
    # Prepare the Dev Server for this build.
    remote_build_dir, exists = self.PrepareDevServer(tag, force=force)

    if not exists:
      # Make a copy of the official build, only take necessary files.
      self.RemoteCommand('cp %s %s %s %s' % (
          os.path.join(self._images, board, build, self.TEST_IMAGE),
          os.path.join(self._images, board, build, self.ROOT_UPDATE),
          os.path.join(self._images, board, build, self.STATEFUL_UPDATE),
          remote_build_dir))

    return remote_build_dir

  def GetControlFile(self, board, build, control):
    """Attempts to pull the requested control file from the Dev Server.

    Args:
      board: Fully qualified board name; e.g., x86-generic-rel
      build: Fully qualified build string; e.g., 0.8.61.0-r1cf43296-b269
      control: Path to control file on remote host relative to Autotest root.

    Returns:
      Contents of the control file.

    Raises:
      common_util.ChromeOSTestError: If control file can't be retrieved
    """
    # Create temporary file to target via scp; close.
    return self.RemoteCommand(
        'cat %s' % posixpath.join(self._images, board, build, control),
        output=True)

  def ListAutoupdateTargets(self, board, build):
    """Returns a list of autoupdate test targets for the given board, build.

    Args:
      board: Fully qualified board name; e.g., x86-generic-rel
      build: Fully qualified build string; e.g., 0.8.61.0-r1cf43296-b269

    Returns:
      List of autoupdate test targets; e.g., ['0.14.747.0-r2bf8859c-b2927_nton']

    Raises:
      common_util.ChromeOSTestError: If control file can't be retrieved
    """
    msg = 'Unable to retrieve list of autoupdate targets!'
    return [os.path.basename(t) for t in self.RemoteCommand(
        'ls -d %s/*' % posixpath.join(self._images, board, build, self.AU_BASE),
        output=True, error_msg=msg).split()]

  def GetImage(self, board, build, staging_dir):
    """Retrieve the TEST_IMAGE for the specified board and build.

    Downloads the image using wget via the Dev Server HTTP interface. The image
    is given a new random file name in the staging directory.

    Args:
      board: Fully qualified board name; e.g., x86-generic-rel
      build: Fully qualified build string; e.g., 0.8.61.0-r1cf43296-b269
      staging_dir: Directory to store downloaded image in.

    Returns:
      File name of the image in the staging directory.
    """
    image_url = '%s/%s' % (
        self.GetUpdateUrl(board, build).replace('update', 'static/archive'),
        self.TEST_IMAGE)
    image_file = self.TEST_IMAGE + '.n-1'
    msg = 'Failed to retrieve the specified image from the Dev Server!'
    common_util.RunCommand(
        'wget -O %s --timeout=30 --tries=1 --no-proxy %s' % (
            image_file, image_url), cwd=staging_dir, error_msg=msg)
    return image_file
