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
                      'debug': {'/D': [{'client.0.DEBUG': {'/S': 5698}},
                                       {'client.0.ERROR': {'/S': 254}},
                                       {'client.0.INFO': {'/S': 1020}},
                                       {'client.0.WARNING': {'/S': 242}}],
                                '/S': 7214}
                      },
              '/S': 7948
            }
}
"""

import argparse
import fnmatch
import json
import os
import time

import result_info
import utils_lib


# Do NOT import autotest_lib modules here. This module can be executed without
# dependency on other autotest modules. This is to keep the logic of result
# trimming on the server side, instead of depending on the autotest client
# module.

DEFAULT_SUMMARY_FILENAME_FMT = 'dir_summary_%d.json'
# Minimum disk space should be available after saving the summary file.
MIN_FREE_DISK_BYTES = 10 * 1024 * 1024

# Autotest uses some state files to track process running state. The files are
# deleted from test results. Therefore, these files can be ignored.
FILES_TO_IGNORE = set([
    'control.autoserv.state'
])

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


def _preprocess_result_dir_path(path):
    """Verify the result directory path is valid and make sure it ends with `/`.

    @param path: A path to the result directory.
    @return: A verified and processed path to the result directory.
    @raise IOError: If the path doesn't exist.
    @raise ValueError: If the path is not a directory.
    """
    if not os.path.exists(path):
        raise IOError('Path %s does not exist.' % path)

    if not os.path.isdir(path):
        raise ValueError('The given path %s is a file. It must be a '
                         'directory.' % path)

    # Make sure the path ends with `/` so the root key of summary json is always
    # utils_lib.ROOT_DIR ('')
    if not path.endswith(os.sep):
        path = path + os.sep

    return path


def _delete_missing_entries(summary_old, summary_new):
    """Delete files/directories only exists in old summary.

    When the new summary is final, i.e., it's built from the final result
    directory, files or directories missing are considered to be deleted and
    trimmed to size 0.

    @param summary_old: Old directory summary.
    @param summary_new: New directory summary.
    """
    new_files = summary_new.get_file_names()
    old_files = summary_old.get_file_names()
    for name in old_files:
        old_file = summary_old.get_file(name)
        if name not in new_files:
            if old_file.is_dir:
                # Trim sub-directories.
                _delete_missing_entries(old_file, result_info.EMPTY)
                old_file.update_sizes()
            elif name in FILES_TO_IGNORE:
                # Remove the file from the summary as it can be ignored.
                summary_old.remove_file(name)
            else:
                # Before setting the trimmed size to 0, update the collected
                # size if it's not set yet.
                if not old_file.is_collected_size_recorded:
                    old_file.collected_size = old_file.trimmed_size
                old_file.trimmed_size = 0
        elif old_file.is_dir:
            # If `name` is a directory in the old summary, but a file in the new
            # summary, delete the entry in the old summary.
            new_file = summary_new.get_file(name)
            if not new_file.is_dir:
                new_file = result_info.EMPTY
            _delete_missing_entries(old_file, new_file)


def _relocate_summary(result_dir, summary_file, summary):
    """Update the given summary with the path relative to the result_dir.

    @param result_dir: Path to the result directory.
    @param summary_file: Path to the summary file.
    @param summary: A directory summary inside the given result_dir or its
            sub-directory.
    @return: An updated summary with the path relative to the result_dir.
    """
    sub_path = os.path.dirname(summary_file).replace(
            result_dir.rstrip(os.sep), '')
    if sub_path == '':
        return summary

    folders = sub_path.split(os.sep)

    # The first folder is always '' because of the leading `/` in sub_path.
    parent = result_info.ResultInfo(
            result_dir, utils_lib.ROOT_DIR, parent_result_info=None)
    root = parent

    # That makes sure root has only one folder of utils_lib.ROOT_DIR.
    for i in range(1, len(folders)):
        child = result_info.ResultInfo(
                parent.path, folders[i], parent_result_info=parent)
        if i == len(folders) - 1:
            # Add files in summary to child.
            for info in summary.files:
                child.files.append(info)

        parent.files.append(child)
        parent = child

    parent.update_sizes()
    return root


def merge_summaries(path):
    """Merge all directory summaries in the given path.

    This function calculates the total size of result files being collected for
    the test device and the files generated on the drone. It also returns merged
    directory summary.

    @param path: A path to search for directory summaries.
    @return a tuple of (client_collected_bytes, merged_summary):
            client_collected_bytes: The total size of results collected from
                the DUT. The number can be larger than the total file size of
                the given path, as files can be overwritten or removed.
            merged_summary: The merged directory summary of the given path.
    """
    path = _preprocess_result_dir_path(path)
    # Find all directory summary files and sort them by the time stamp in file
    # name.
    summary_files = []
    for root, _, filenames in os.walk(path):
        for filename in fnmatch.filter(filenames, 'dir_summary_*.json'):
            summary_files.append(os.path.join(root, filename))

    summary_files = sorted(summary_files, key=os.path.getmtime)

    all_summaries = []
    for summary_file in summary_files:
        try:
            summary = result_info.load_summary_json_file(summary_file)
            summary = _relocate_summary(path, summary_file, summary)
            all_summaries.append(summary)
        except (IOError, ValueError) as e:
            utils_lib.LOG('Failed to load summary file %s Error: %s' %
                          (summary_file, e))

    # Merge all summaries.
    merged_summary = all_summaries[0] if len(all_summaries) > 0 else None
    for summary in all_summaries[1:]:
        merged_summary.merge(summary)
    # After all summaries from the test device (client side) are merged, we can
    # get the total size of result files being transfered from the test device.
    # If there is no directory summary collected, default client_collected_bytes
    # to 0.
    client_collected_bytes = 0
    if merged_summary:
        client_collected_bytes = merged_summary.collected_size

    # Get the summary of current directory
    last_summary = result_info.ResultInfo.build_from_path(path)

    if merged_summary:
        merged_summary.merge(last_summary, is_final=True)
        _delete_missing_entries(merged_summary, last_summary)
    else:
        merged_summary = last_summary

    return client_collected_bytes, merged_summary


def main():
    """main script. """
    parser = argparse.ArgumentParser()
    parser.add_argument('-p', type=str, dest='path',
                        help='Path to build directory summary.')
    parser.add_argument('-m', type=int, dest='max_size_KB', default=0,
                        help='Maximum result size in KB. Set to 0 to disable '
                        'result throttling.')
    options = parser.parse_args()

    path = _preprocess_result_dir_path(options.path)
    summary = result_info.ResultInfo.build_from_path(path)

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
    utils_lib.LOG('Directory summary of %s is saved to file %s.' %
                  (options.path, summary_file))


if __name__ == '__main__':
    main()
