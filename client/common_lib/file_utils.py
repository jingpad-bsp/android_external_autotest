# Copyright (c) 2014 The Chromium OS Authors. All rights reserved.
# Use of this source code is governed by a BSD-style license that can be
# found in the LICENSE file.

import errno
import os
import shutil


def rm_dir_if_exists(dir_to_remove):
    """
    Removes a directory. Does not fail if the directory does NOT exist.

    @param dir_to_remove: path, directory to be removed.

    """
    try:
        shutil.rmtree(dir_to_remove)
    except OSError as e:
        if e.errno != errno.ENONET:
            raise


def rm_dirs_if_exist(dirs_to_remove):
    """
    Removes multiple directories. Does not fail if directories do NOT exist.

    @param dirs_to_remove: list of directory paths to be removed.

    """
    for dr in dirs_to_remove:
        rm_dir_if_exists(dr)


def ensure_file_exists(filepath):
    """
    Verifies path given points to an existing file.

    @param filepath: path, path to check.

    @raises IOError if the path given does not point to a valid file.

    """
    error_msg = 'File %s does not exist.' % filepath
    if not os.path.isfile(filepath):
        raise IOError(error_msg)


def ensure_all_files_exist(filepaths):
    """
    Verifies all paths given point to existing files.

    @param filepaths: List of paths to check.

    @raises IOError if given paths do not point to existing files.

    """
    for filepath in filepaths:
        ensure_file_exists(filepath)


def ensure_dir_exists(dirpath):
    """
    Verifies path given points to an existing directory.

    @param dirpath: path, dir to check.

    @raises IOError if path does not point to an existing directory.

    """
    error_msg = 'Directory %s does not exist.' % dirpath
    if not os.path.isdir(dirpath):
        raise IOError(error_msg)


def ensure_all_dirs_exist(dirpaths):
    """
    Verifies all paths given point to existing directories.

    @param dirpaths: list of directory paths to check.

    @raises IOError if given paths do not point to existing directories.

    """
    for dirpath in dirpaths:
        ensure_dir_exists(dirpath)


def make_leaf_dir(dirpath):
    """
    Creates a directory, also creating parent directories if they do not exist.

    @param dirpath: path, directory to create.

    @raises whatever exception raised other than "path already exist".

    """
    try:
        os.makedirs(dirpath)
    except OSError as e:
        if e.errno != errno.EEXIST:
            raise


def make_leaf_dirs(dirpaths):
    """
    Creates multiple directories building all respective parent directories if
    they do not exist.

    @param dirpaths: list of directory paths to create.

    @raises whatever exception raised other than "path already exists".
    """
    for dirpath in dirpaths:
        make_leaf_dir(dirpath)