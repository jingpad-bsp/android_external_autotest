#!/usr/bin/python
#
# Copyright (c) 2011 The Chromium OS Authors. All rights reserved.
# Use of this source code is governed by a BSD-style license that can be
# found in the LICENSE file.

"""A common build utility library used by other Chrome OS scripts.

Various helper functions for checking build versions, downloading builds,
processing Chrome OS build components, and extracting tests.
"""

__author__ = 'dalecurtis@google.com (Dale Curtis)'

import logging
import os
import re
import tempfile
import urlparse

import common_util


# Name of autotest tarball in downloaded archive.
AUTOTEST = 'autotest.tar'

# Directory to mount rootfs to during MountImage.
ROOTFS_MOUNT_DIR = 'rootfs'

# Relative path to scripts directory from Chrome OS source root.
SCRIPTS_DIR = 'src/scripts'

# Directory to mount stateful partition to during MountImage.
STATEFUL_MOUNT_DIR = 'stateful_partition'

# Name of test image in downloaded archive.
TEST_IMAGE = 'chromiumos_test_image.bin'


def GetLatestBuildbotBuildVersion(archive_server, board, boto=None,
                                  archive_path=None, build_pattern=None):
  """Retrieves the latest build version from Buildbot for the given board.

  Uses gsutil to build a list of builds matching the archive_path and
  build_pattern after wildcard expansion, sorts it by timestamp, and returns the
  latest build.

  Args:
    archive_server: Base Google Storage URL.
    board: Board name for this build; e.g., x86-generic-rel
    boto: If a Google Storage URL is provided, path to credentials file for use
        with gsutil; e.g., ~/.boto
    archive_path: Path to image file. Will be joined with archive_server.
        %(build)s values will be expanded with build_pattern if provided,
        otherwise *. All other format variables will be expanded as *.
    build_pattern: Wildcard expansion for %(build)s variable in archive_path.

  Returns:
    Latest build version; e.g., 0.8.61.0-r1cf43296-b269.

  Raises:
    common_util.ChromeOSTestError: if the latest build version can't be
        retrieved.
  """
  if not build_pattern:
    build_pattern = '*'

  # Create RegEx for extracting the build from the URL.
  regex_path = archive_path % {'board': '[\w-]+', 'build': '([\.\w-]+)',
                               'build_version': '[\.\w-]+'}

  # Wildcard expansion for the Google Storage URL...
  archive_path %= {'board': '*', 'build': build_pattern, 'build_version': '*'}

  archive_url = '/'.join([archive_server, archive_path])
  regex_url = '/'.join([archive_server, regex_path])

  env = {}
  if boto:
    env['BOTO_CONFIG'] = boto

  # Run gsutil, strip last line, sort by timestamp, extract URL.
  cmd = ("gsutil ls -l %s | sed '$d' | sort -k 2,2 | tail -1 |"
         " awk '{print $3}'" % archive_url)
  msg = 'Could not retrieve latest build version for board %s.' % board
  latest_url = common_util.RunCommand(
      cmd=cmd, env=env, error_msg=msg, output=True)

  if latest_url:
    # Fail loudly here by letting exception raise on unrecognized format.
    return re.match(regex_url, latest_url).group(1)


def DownloadAndExtractBuild(archive_server, board, boto, build,
                            archive_path=None):
  """Downloads the specified build and extracts it to a temporary folder.

  Looks for the file '<archive_server>/<board>/<build>/image.zip'. The archive
  is expected to contain chromiumos_test_image.bin and autotest.tar. Both
  Google Storage and http(s) URLs are okay. If a Google Storage URL is provided,
  gsutil is used to download the file, while for http(s) wget is used. wget and
  gsutil must be in the path. Downloaded archive is deleted if all steps
  complete successfully.

  Args:
    archive_server: Google Storage or http(s) archive URL.
    board: Board name for this build; e.g., x86-generic-rel
    boto: If a Google Storage URL is provided, path to credentials file for use
        with gsutil; e.g., ~/.boto
    build: Full build string to look for; e.g., R16-1000.0.0-a1-b269
    archive_path: Optional path to image on the archive server. Will be
        formatted against:
        {
          'board': <e.g. 'x86-generic-rel'>,
          'build': <e.g. 'R16-1000.0.0-a1-b269'>,
          'build_version': <e.g. '1000.0.0'>,
        }

  Returns:
    A tuple of two paths (local_staging_dir, remote_arhive_path)
        local_staging_dir is the path to the staging directory where the build
            has been downloaded and relevant components extracted.
        remote_archive_url is the path where the image was downloaded from
            remote site.

  Raises:
    common_util.ChromeOSTestError: If any steps in the process fail to complete.
  """
  if archive_path is None:
    archive_path = '%(board)s/%(build)s/image.zip'

  # Format user specified archive path against parsed build variables.
  build_release = ''
  build_version, build_hash, build_num = build.rsplit('-', 2)
  if '-' in build_version:
    build_release, build_version = build_version.split('-')
  archive_path %= {'board': board, 'build': build,
                   'build_version': build_version}
  archive_url = '/'.join([archive_server, archive_path])

  # Create temporary directory for extraction and processing of build.
  staging_dir = tempfile.mkdtemp()

  # Standardize file name of archive to be downloaded.
  download_path = os.path.join(staging_dir, 'image.zip')

  env = {}

  # Choose download method based on URL protocol.
  scheme = urlparse.urlparse(archive_url).scheme
  if scheme == 'gs':
    if boto:
      env['BOTO_CONFIG'] = boto
    cmd = 'gsutil cp %s %s' % (archive_url, download_path)
  elif scheme in ['http', 'https']:
    cmd = 'wget -O %s --no-proxy %s' % (download_path, archive_url)
  else:
    raise common_util.ChromeOSTestError('Unknown archive URL protocol.')

  msg = 'Failed to download build! Tried "%s"' % archive_url
  common_util.RunCommand(cmd=cmd, env=env, error_msg=msg)

  # Extract test image and autotest tarball.
  cmd = 'unzip -u -o %s %s %s' % (download_path, TEST_IMAGE, AUTOTEST)
  msg = 'Failed to extract build!'
  common_util.RunCommand(cmd=cmd, cwd=staging_dir, error_msg=msg)

  # Extract autotest components. Use root to ensure when files are inserted into
  # the image later, that they have the proper permissions. Failure to do so
  # will break certain tests.
  cmd = 'sudo tar xf %s' % os.path.join(staging_dir, AUTOTEST)
  msg = 'Failed to extract autotest.tar !'
  common_util.RunCommand(cmd=cmd, cwd=staging_dir, error_msg=msg)

  # Everything went okay, so remove archive file.
  os.unlink(download_path)
  return staging_dir, archive_url


def CreateUpdateZip(cros_checkout, staging_dir, image_file=TEST_IMAGE,
                    output_dir=None, source_image=None):
  """Create update.gz from an image using cros_generate_update_payload.

  Args:
    cros_checkout: Location of a ChromeOS source code check out. A valid chroot
        is required to call the cros_generate_update_payload script.
    staging_dir: Work directory. Should contain a ChromeOS image.
    image_file: Name of the image to process.
    output_dir: Path relative to staging_dir to store update.gz in. Defaults to
        the root of the staging_dir.
    source_image: If specified, used to generate a delta update. Must be located
        in the chroot.

  Raises:
    common_util.ChromeOSTestError: If any steps in the process fail to complete.
  """
  # Create mount point for image temp in ChromeOS chroot.
  chroot_dir = os.path.join(cros_checkout, 'chroot')
  in_chroot_dir = os.sep + os.path.relpath(
      tempfile.mkdtemp(dir=os.path.join(chroot_dir, 'tmp')), chroot_dir)
  # Skip '/' in in_chroot_dir otherwise os.path.join will treat it as an
  # absolute path and reset the whole join.
  out_chroot_dir = os.path.join(chroot_dir, in_chroot_dir[1:])

  # Mount staging directory into the chroot.
  cmd = 'sudo mount --bind %s %s' % (staging_dir, out_chroot_dir)
  msg = 'Failed to mount image directory in chroot!'
  common_util.RunCommand(cmd=cmd, error_msg=msg)

  scripts_dir = os.path.join(cros_checkout, SCRIPTS_DIR)

  update_path = in_chroot_dir
  if output_dir:
    update_path = os.path.join(update_path, output_dir)

  # Use cros_generate_update_payload in the chroot to create update.gz.
  # TODO(dalecurtis): May need to add special failure case for lazy unmounts, no
  # sense in aborting if the only issue is we can't unmount the staging dir.
  cmd = ('cros_sdk -- cros_generate_update_payload --image %s --output %s' %
         (os.path.join(in_chroot_dir, image_file),
          os.path.join(update_path, 'update.gz')))

  if source_image:
    cmd += ' --src_image %s' % os.path.join(in_chroot_dir, source_image)

  msg = 'Failed to create update.gz!'
  # cros_generate_update_payload is a frequent source of errors. Which is why we
  # want to set error_file=True so the errors will appear in the logs.
  common_util.RunCommand(
      cmd=cmd, cwd=scripts_dir, error_msg=msg, error_file=True)

  # Unmount chroot temp directory. Exit chroot unmounts automatically only if
  # there are no other cros_sdk instances open.
  cmd = 'sudo umount ' + out_chroot_dir
  common_util.RunCommand(cmd=cmd, ignore_errors=True)

  # Remove mount point.
  os.rmdir(out_chroot_dir)


def MountImage(cros_checkout, staging_dir, image_file=TEST_IMAGE,
               image_dir='.'):
  """Mount an image to ROOTFS_MOUNT_DIR and STATEFUL_MOUNT_DIR in staging_dir.

  Uses mount_gpt_image.sh from outside the chroot to setup the mounts. Image is
  mounted in safe mode (read only rootfs).

  Args:
    cros_checkout: Location of a ChromeOS source code check out. A valid chroot
        is required to call the cros_generate_update_payload script.
    staging_dir: Work directory. Should also contain a ChromeOS image. If the
        image is elsewhere, specify using image_dir.
    image_file: Name of the image to process.
    image_dir: The directory of the image, using staging_dir if not given.
  """
  scripts_dir = os.path.join(cros_checkout, SCRIPTS_DIR)
  # Mount rootfs and stateful partitions. Mount rootfs as read_only.
  common_util.MakedirsExisting(os.path.join(staging_dir, ROOTFS_MOUNT_DIR))
  common_util.MakedirsExisting(os.path.join(staging_dir,
                                            STATEFUL_MOUNT_DIR))
  cmd = ('sudo %s/mount_gpt_image.sh --image %s --from %s --rootfs_mountpt=%s'
         ' --stateful_mountpt=%s --safe' % (scripts_dir, image_file, image_dir,
         ROOTFS_MOUNT_DIR, STATEFUL_MOUNT_DIR))
  msg = 'Failed to mount partitions!'
  common_util.RunCommand(cmd=cmd, cwd=staging_dir, error_msg=msg)


def UnmountImage(cros_checkout, staging_dir):
  """Unmount image in staging_dir from ROOTFS_MOUNT_DIR and STATEFUL_MOUNT_DIR.

  Uses mount_gpt_image.sh from outside the chroot to teardown the mounts.

  Args:
    cros_checkout: Location of a ChromeOS source code check out. A valid chroot
        is required to call the cros_generate_update_payload script.
    staging_dir: Work directory. Should also contain a ChromeOS image. If the
        image is elsewhere, specify using image_dir.
  """
  scripts_dir = os.path.join(cros_checkout, SCRIPTS_DIR)

  # Unmount partitions.
  cmd = ('sudo %s/mount_gpt_image.sh --unmount --rootfs_mountpt=%s'
         ' --stateful_mountpt=%s' %
         (scripts_dir, ROOTFS_MOUNT_DIR, STATEFUL_MOUNT_DIR))
  msg = 'Failed to unmount partitions!'
  common_util.RunCommand(cmd=cmd, cwd=staging_dir, error_msg=msg)


def PrepareAutotestPkgs(autotest_dir, staging_dir, test_name='all'):
  """Create autotest client packages inside staging_dir.

  So they could be uploaded later, either to a mounted stateful partition or a
  remote dev server.

  Args:
    autotest_dir: Location of Autotest directory. Absolute or relative to the
        staging_dir.
    staging_dir: Work directory. Should also contain a ChromeOS image. If the
        image is elsewhere, specify using image_dir.
    test_name: Name of test to package. Defaults to all tests.

  Raises:
    common_util.ChromeOSTestError: If any steps in the process fail to complete.
  """
  common_util.MakedirsExisting(os.path.join(staging_dir, 'autotest-pkgs'))

  cmd_list = ['sudo', os.path.join(autotest_dir, 'utils/packager.py'),
              'upload', '--repository autotest-pkgs']
  if test_name == 'all':
    cmd_list.append('--all')
  else:
    cmd_list.append('--client --test ' + test_name)

  # Upload autotest packages onto remote server.
  msg = 'Failed to create autotest packages!'
  common_util.RunCommand(cmd=' '.join(cmd_list), cwd=staging_dir,
                         error_msg=msg)


def CreateStatefulZip(cros_checkout, staging_dir, image_file=TEST_IMAGE):
  """Create stateful.tgz from using cros_generate_stateful_update_payload.

  Args:
    cros_checkout: Location of a ChromeOS source code check out. A valid chroot
        is required to call the cros_generate_update_payload script.
    staging_dir: Work directory. Should also contain a ChromeOS image. If the
        image is elsewhere, specify using image_dir.
    image_file: Name of the image to process.

  Raises:
    common_util.ChromeOSTestError: If any steps in the process fail to complete.
  """
  chroot_bin_dir = os.path.join(cros_checkout, 'chroot/usr/bin')

  # Generate stateful update.
  cmd = ('sudo %s/cros_generate_stateful_update_payload --image_path %s '
         '--output_dir .' % (chroot_bin_dir, image_file))
  msg = 'Failed to generate stateful.tgz!'
  common_util.RunCommand(cmd=cmd, cwd=staging_dir, error_msg=msg)


def CreateBuildComponents(cros_checkout, staging_dir):
  """Creates various build components from chromiumos_test_image.bin.

  Given a staging directory containing a chromiumos_test_image.bin and autotest
  tarball, method creates update.gz and stateful.image.gz.

  Args:
    cros_checkout: Location of a ChromeOS source code check out. A valid chroot
        is required to call the cros_generate_update_payload script.
    staging_dir: Directory containing unzipped Buildbot image.

  Raises:
    common_util.ChromeOSTestError: If any steps in the process fail to complete.
  """
  CreateUpdateZip(cros_checkout, staging_dir)
  PrepareAutotestPkgs('autotest', staging_dir)
  CreateStatefulZip(cros_checkout, staging_dir)
