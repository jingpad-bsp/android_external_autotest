#!/usr/bin/env python
# Copyright (c) 2010 The Chromium OS Authors. All rights reserved.
# Use of this source code is governed by a BSD-style license that can be
# found in the LICENSE file.

"""Provides convenience routines to access the GBB on the current BIOS.

   GBBUtility is a wrapper of gbb_utility program.
"""

import os
import tempfile

from autotest_lib.client.bin import utils
from autotest_lib.client.common_lib import error
import common
import flashrom_util


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
        self._need_commit = False
        self._gbb_file = None
        self._clear_cached()


    def __del__(self):
        if self._gbb_file:
            self._remove_temp_file(self._gbb_file)
        if self._need_commit:
            raise error.TestError(
                'You changed somethings; should commit or discard them.')


    def _clear_cached(self):
        if self._gbb_file:
            self._remove_temp_file(self._gbb_file)
        self._gbb_file = None
        self._bmpfv = None
        self._recoverykey = None
        self._rootkey = None
        self._hwid = None


    def _get_temp_filename(self, prefix='tmp_'):
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


    def _get_current_gbb_file(self):
        """Gets the GBB in BIOS to a file, self._gbb_file."""
        if not self._gbb_file:
            flashrom = flashrom_util.FlashromUtility()
            flashrom.initialize(flashrom.TARGET_BIOS)

            gbb_data = flashrom.read_section('FV_GBB')
            gbb_file = self._get_temp_filename('current_gbb_')
            utils.open_write_close(gbb_file, gbb_data)
            self._gbb_file = gbb_file

        return self._gbb_file


    def _run_gbb_utility(self, args, output_file=''):
        """Runs gbb_utility on the current BIOS firmware data."""
        gbb_file = self._get_current_gbb_file()
        cmd = 'gbb_utility %s "%s" "%s"' % (args, gbb_file, output_file)
        result = utils.system_output(cmd)
        return result


    def _get_gbb_value(self, key):
        """Gets the GBB value which needs to be output to a file in gbb_utility.

        @param key: The key of the value you want to get. Should be 'bmfv',
            'recoverykey', or 'rootkey'.
        @return: The returned GBB value.
        """
        value_file = self._get_temp_filename('get_%s_' % key)
        self._run_gbb_utility('--get --%s=%s' % (key, value_file))
        value = utils.read_file(value_file)
        self._remove_temp_file(value_file)
        return value


    def get_bmpfv(self):
        if not self._bmpfv:
            self._bmpfv = self._get_gbb_value('bmpfv')
        return self._bmpfv


    def get_hwid(self):
        if not self._hwid:
            result = _self._run_gbb_utility(self, '--get --hwid')
            self._hwid = result.strip().partition('hardware_id: ')[2]
        return self._hwid


    def get_recoverykey(self):
        if not self._recoverykey:
            self._recoverykey = self._get_gbb_value('recoverykey')
        return self._recoverykey


    def get_rootkey(self):
        if not self._rootkey:
            self._rootkey = self._get_gbb_value('rootkey')
        return self._rootkey


    def set_bmpfv(self, bmpfv):
        self._bmpfv = bmpfv
        self._need_commit = True


    def set_hwid(self, hwid):
        self._hwid = hwid
        self._need_commit = True


    def set_recoverykey(self, recoverykey):
        self._recoverykey = recoverykey
        self._need_commit = True


    def set_rootkey(self, rootkey):
        self._rootkey = rootkey
        self._need_commit = True


    def commit(self):
        """Commit all changes to the current BIOS."""
        if self._need_commit:
            args = '--set'
            if self._bmpfv:
                bmpfv_file = self._get_temp_filename('set_bmpfv_')
                utils.open_write_close(bmpfv_file, self._bmpfv)
                args += ' --bmpfv=%s' % bmpfv_file
            if self._hwid:
                args += ' --hwid="%s"' % self._hwid
            if self._recoverykey:
                recoverykey_file = self._get_temp_filename('set_recoverykey_')
                utils.open_write_close(recoverykey_file, self._recoverykey)
                args += ' --recoverykey=%s' % recoverykey_file
            if self._rootkey:
                rootkey_file = self._get_temp_filename('set_rootkey_')
                utils.open_write_close(rootkey_file, self._rootkey)
                args += ' --rootkey=%s' % rootkey_file

            flashrom = flashrom_util.FlashromUtility()
            flashrom.initialize(flashrom.TARGET_BIOS)

            new_gbb_file = self._get_temp_filename('new_gbb_')
            self._run_gbb_utility(args, output_file=new_gbb_file)
            new_gbb = utils.read_file(new_gbb_file)

            flashrom.write_section('FV_GBB', new_gbb)
            flashrom.commit()

            if self._bmpfv:
                self._remove_temp_file(bmpfv_file)
            if self._recoverykey:
                self._remove_temp_file(recoverykey_file)
            if self._rootkey:
                self._remove_temp_file(rootkey_file)
            self._need_commit = False
            self._clear_cached()


    def discard(self):
        """Discard all uncommitted changes."""
        if self._need_commit:
            self._need_commit = False
            self._clear_cached()
