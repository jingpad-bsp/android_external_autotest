#!/usr/bin/python3
#
# Copyright 2017 The Android Open-Source Project
#
# Licensed under the Apache License, Version 2.0 (the "License");
# you may not use this file except in compliance with the License.
# You may obtain a copy of the License at
#
#      http://www.apache.org/licenses/LICENSE-2.0
#
# Unless required by applicable law or agreed to in writing, software
# distributed under the License is distributed on an "AS IS" BASIS,
# WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied.
# See the License for the specific language governing permissions and
# limitations under the License.

"""Generates an Android fs_config file for mksquashfs.

mksquashfs ignores any file-based capabilities in the filesystem when
constructing the image. Instead, it loads them from an "fs_config" file,
which must contain every single file and directory entry.
"""

from __future__ import print_function

import argparse
import errno
import logging
import os
import struct


def _get_file_based_capabilities(path):
  """Get the file-based capabilities of |path| as an integer.

  Returns None if |path| does not have any file-based capabilities.
  """
  # The name of the extended filesystem attribute that stores capabilities.
  CAPABILITY_NAME = 'security.capability'
  VFS_CAP_REVISION = 0x02000000
  VFS_CAP_FLAGS_EFFECTIVE = 0x000001
  ANDROID_VFS_CAP_MAGIC = VFS_CAP_REVISION | VFS_CAP_FLAGS_EFFECTIVE

  try:
    vfs_cap_data = os.getxattr(path, CAPABILITY_NAME,
                               follow_symlinks=False)
    # The vfs_cap_data structure is serialized into the security.capability
    # xattr. The structure itself is defined in
    # http://elixir.free-electrons.com/linux/v4.4/source/include/uapi/linux/capability.h#L69
    magic, p_low, _, p_high, _ = struct.unpack('<IIIII', vfs_cap_data)
    if magic != ANDROID_VFS_CAP_MAGIC:
      raise EnvironmentError('Wrong magic value in %s: %x, expected %x' %
                             (path, magic, ANDROID_VFS_CAP_MAGIC))
    return (p_high << 32) | p_low
  except OSError as e:
    if e.errno == errno.ENODATA:
      # This is expected of any file that has no file-based capabilities
      return None
    else:
      raise


def generate_android_fs_config(directory, mount_point, output):
  """Generates the Android fs_config for |directory| into |output|.

  |output| should be an opened file, and will be flushed afterwards.
  """
  def _generate_one_entry(path):
    stat = os.lstat(path)
    if path == directory:
      # The root of the filesystem uses an empty filename.
      canned_entry_path = ''
    else:
      canned_entry_path = os.path.join(mount_point,
                                       os.path.relpath(path, directory))
    # Strip the leading / because NYC's mksquashfs doesn't like absolute
    # paths.
    canned_entry = ('%s %d %d %o' % (canned_entry_path[1:], stat.st_uid,
                                     stat.st_gid, stat.st_mode))
    capabilities = _get_file_based_capabilities(path)
    if capabilities:
      canned_entry += ' capabilities=0x%x' % capabilities
    logging.debug('Adding %s to Android fs_config file', canned_entry)
    output.write('%s\n' % canned_entry)
  # Make the mountpoint absolute without querying the filesystem.
  mount_point = os.path.join('/', mount_point)
  _generate_one_entry(directory)
  for root, dirs, files in os.walk(directory):
    for name in files + dirs:
      _generate_one_entry(os.path.join(root, name))
  output.flush()


def main():
  parser = argparse.ArgumentParser(
      formatter_class=argparse.RawDescriptionHelpFormatter,
      description=__doc__)
  parser.add_argument(
      '--output', type=argparse.FileType('w'), help='The file to write to.')
  parser.add_argument(
      '--mount-point', default='/', help='The mount point of the image.')
  parser.add_argument(
      '--loglevel', default='INFO',
      choices=('DEBUG', 'INFO', 'WARNING', 'ERROR', 'CRITICAL'),
      help='Logging level.')
  parser.add_argument('directory', type=str, help='The root of the files.')
  args = parser.parse_args()

  logging.basicConfig(level=getattr(logging, args.loglevel))

  generate_android_fs_config(args.directory, args.mount_point, args.output)

if __name__ == '__main__':
  main()
