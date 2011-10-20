# Copyright (c) 2011 The Chromium OS Authors. All rights reserved.
# Use of this source code is governed by a BSD-style license that can be
# found in the LICENSE file.

import common
import compiler, logging, os, random, re, time
from autotest_lib.client.common_lib import control_data, error, utils


class ControlFileGetter(object):
    """
    Interface for classes that can list and fetch known control files.

    @var _CONTROL_PATTERN: control file name format to match.
    """

    _CONTROL_PATTERN = '^control(?:\..+)?$'

    def __init__(self):
        pass


    def get_control_file_list(self):
        """
        Gather a list of paths to control files matching |_CONTROL_PATTERN|.

        @return A list of files that match regexp
        """
        pass


    def get_control_file_contents(self, test_path):
        """
        Given a path to a control file, return its contents.

        @param test_path: the path to the control file
        @return the contents of the control file specified by the path.
        """
        pass


    def get_control_file_contents_by_name(self, test_name):
        """
        Given the name of a control file, return its contents.

        @param test_name: the path to the control file.
        @return the contents of the control file specified by the path.
        """
        pass


    def _is_useful_file(self, name):
        return '__init__.py' not in name and '.svn' not in name


class FileSystemGetter(ControlFileGetter):
    def __init__(self, paths):
        """
        @param paths: base directories to start search.
        """
        self._paths = paths
        self._files = []


    def get_control_file_list(self):
        """
        Gather a list of paths to control files under |_paths|.

        @return A list of files that match |_CONTROL_PATTERN|.
        """
        regexp = re.compile(self._CONTROL_PATTERN)
        directories = self._paths
        while len(directories) > 0:
            directory = directories.pop()
            if not os.path.exists(directory):
                continue
            for name in os.listdir(directory):
                fullpath = os.path.join(directory, name)
                if os.path.isfile(fullpath):
                    if regexp.search(name):
                        # if we are a control file
                        self._files.append(fullpath)
                elif os.path.isdir(fullpath):
                    directories.append(fullpath)
        return [f for f in self._files if self._is_useful_file(f)]


    def get_control_file_contents(self, test_path):
        return utils.read_file(test_path)


    def get_control_file_contents_by_name(self, test_name):
        if not self._files:
            self.get_control_file_list()
        regexp = re.compile(os.path.join(test_name, 'control'))
        candidates = filter(regexp.search, self._files)
        if not candidates or len(candidates) > 1:
            raise error.TestError(test_name + ' is not unique.')
        return self.get_control_file_contents(candidates[0])
