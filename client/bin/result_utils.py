#!/usr/bin/python
# Copyright 2017 The Chromium OS Authors. All rights reserved.
# Use of this source code is governed by a BSD-style license that can be
# found in the LICENSE file.

"""
This is a utility to build a summary of the given directory. and save to a json
file.

Example usage:
    result_utils.py -p path

The content of the json file looks like:
{'default': {'/D': {'control': {'/S': 734},
                      'debug': {'/D': {'client.0.DEBUG': {'/S': 5698},
                                       'client.0.ERROR': {'/S': 254},
                                       'client.0.INFO': {'/S': 1020},
                                       'client.0.WARNING': {'/S': 242}},
                                '/S': 7214}
                      },
              '/S': 7948
            }
}
"""

import argparse
import json
import logging
import os
import time


DEFAULT_SUMMARY_FILENAME_FMT = 'dir_summary_%d.json'
# Minimum disk space should be available after saving the summary file.
MIN_FREE_DISK_BYTES = 10 * 1024 * 1024

# Key names for directory summaries. The keys are started with / so it can be
# differentiated with a valid file name. The short keys are designed for smaller
# file size of the directory summary.
# Size of the directory or file
TOTAL_SIZE_BYTES = '/S'
# A dictionary of sub-directories' summary: name: {directory_summary}
DIRS = '/D'


def get_unique_dir_summary_file(path):
    """Get a unique file path to save the directory summary json string.

    @param path: The directory path to save the summary file to.
    """
    summary_file = DEFAULT_SUMMARY_FILENAME_FMT % time.time()
    # Make sure the summary file name is unique.
    file_name = os.path.join(path, summary_file)
    if os.path.exists(file_name):
        count = 1
        name, ext = os.path.splitext(summary_file)
        while os.path.exists(file_name):
            file_name = os.path.join(path, '%s_%s%s' % (name, count, ext))
            count += 1
    return file_name


def get_dir_summary(path, top_dir, all_dirs=set()):
    """Get the directory summary for the given path.

    @param path: The directory to collect summary.
    @param top_dir: The top directory to collect summary. This is to check if a
            directory is a subdir of the original directory to collect summary.
    @param all_dirs: A set of paths that have been collected. This is to prevent
            infinite recursive call caused by symlink.

    @return: A dictionary of the directory summary.
    """
    dir_info = {}
    dir_info[TOTAL_SIZE_BYTES] = 0
    summary = {os.path.basename(path): dir_info}

    if os.path.isfile(path):
        dir_info[TOTAL_SIZE_BYTES] = os.stat(path).st_size
    else:
        dir_info[DIRS] = {}
        real_path = os.path.realpath(path)
        # The assumption here is that results are copied back to drone by
        # copying the symlink, not the content, which is true with currently
        # used rsync in cros_host.get_file call.
        # Skip scanning the child folders if any of following condition is true:
        # 1. The directory is a symlink and link to a folder under `top_dir`.
        # 2. The directory was scanned already.
        if ((os.path.islink(path) and real_path.startswith(top_dir)) or
            real_path in all_dirs):
            return summary

        all_dirs.add(real_path)
        for f in sorted(os.listdir(path)):
            f_summary = get_dir_summary(os.path.join(path, f), top_dir,
                                        all_dirs)
            dir_info[DIRS][f] = f_summary[f]
            dir_info[TOTAL_SIZE_BYTES] += f_summary[f][TOTAL_SIZE_BYTES]

    return summary


def build_summary_json(path):
    """Build summary of files in the given path and return a json string.

    @param path: The directory to build summary.
    @return: A json string of the directory summary.
    @raise IOError: If the given path doesn't exist.
    """
    if not os.path.exists(path):
        raise IOError('Path %s does not exist.' % path)

    return get_dir_summary(path, top_dir=path)


def main():
    """main script. """
    parser = argparse.ArgumentParser()
    parser.add_argument('-p', type=str, dest='path',
                        help='Path to build directory summary.')
    options = parser.parse_args()

    summary = build_summary_json(options.path)
    summary_json = json.dumps(summary)
    summary_file = get_unique_dir_summary_file(options.path)

    # Make sure there is enough free disk to write the file
    stat = os.statvfs(options.path)
    free_space = stat.f_frsize * stat.f_bavail
    if free_space - len(summary_json) < MIN_FREE_DISK_BYTES:
        raise IOError('Not enough disk space after saving the summary file. '
                      'Available free disk: %s bytes. Summary file size: %s '
                      'bytes.' % (free_space, len(summary_json)))

    with open(summary_file, 'w') as f:
        f.write(summary_json)
    logging.info('Directory summary of %s is saved to file %s.', options.path,
                 summary_file)


if __name__ == '__main__':
    main()
