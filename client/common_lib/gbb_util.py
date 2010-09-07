#!/usr/bin/env python
# Copyright (c) 2010 The Chromium OS Authors. All rights reserved.
# Use of this source code is governed by a BSD-style license that can be
# found in the LICENSE file.

"""Provides convenience routines to access the GBB on the current BIOS.

   GBBUtility is a wrapper of gbb_utility program.
"""

import os
import tempfile

from autotest_lib.client.common_lib import error
from autotest_lib.client.common_lib import flashrom_util
from autotest_lib.client.common_lib import utils


class GBBUtility(object):
    """GBBUtility is a wrapper of gbb_utility program.

    It accesses the GBB on the current BIOS image.
    """
    def __init__(self,
                 gbb_command='gbb_utility',
                 temp_dir=None,
                 keep_temp_files=False):
        self._gbb_command = gbb_command
        self._temp_dir = temp_dir
        self._keep_temp_files = keep_temp_files
        self._bios_file = None


    def __del__(self):
        if self._bios_file:
            self._remove_temp_file(self._bios_file)


    def _get_temp_filename(self, prefix='tmp'):
        """Returns the name of a temporary file in self._temp_dir."""
        (fd, name) = tempfile.mkstemp(prefix=prefix, dir=self._temp_dir)
        os.close(fd)
        return name


    def _remove_temp_file(self, filename):
        """Removes a temporary file if self._keep_temp_files is false."""
        if self._keep_temp_files:
            return
        if os.path.exists(filename):
            os.remove(filename)


    def _read_bios(self, force=False):
        """Reads the BIOS to a file, self._bios_file."""
        if not self._bios_file or force:
            flashrom = flashrom_util.flashrom_util()
            if not flashrom.select_bios_flashrom():
                raise error.TestError('Unable to select BIOS flashrom')
            bios_file = self._get_temp_filename('bios')
            if not flashrom.read_whole_to_file(bios_file):
                raise error.TestError('Unable to read the BIOS image')
            self._bios_file = bios_file


    def _run_gbb_utility(self, args='', output_file=''):
        """Runs gbb_utility on the current BIOS firmware data."""
        self._read_bios()
        cmd = 'gbb_utility %s "%s" "%s"' % (args, self._bios_file,
                                            output_file)
        result = utils.system_output(cmd)
        return result


    def _get_gbb_value(self, key):
        """Gets the GBB value which needs to be output to a file in gbb_utility.

        @param key: The key of the value you want to get. Should be 'bmfv',
            'recoverykey', or 'rootkey'.
        @return: The returned GBB value.
        """
        value_file = self._get_temp_filename(key)
        self._run_gbb_utility('--get --%s=%s' % (key, value_file))
        with open(value_file, 'rb') as f:
            value = f.read()
        self._remove_temp_file(value_file)
        return value


    def get_bmpfv(self):
        return self._get_gbb_value('bmpfv')


    def get_hwid(self):
        result = _self._run_gbb_utility(self, '--get --hwid')
        return result.strip().partition('hardware_id: ')[2]


    def get_recoverykey(self):
        return self._get_gbb_value('recoverykey')


    def get_rootkey(self):
        return self._get_gbb_value('rootkey')
