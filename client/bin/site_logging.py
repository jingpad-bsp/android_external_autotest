# Copyright (c) 2010 The Chromium OS Authors. All rights reserved.
# Use of this source code is governed by a BSD-style license that can be
# found in the LICENSE file.

import logging, os, re
from autotest_lib.client.bin import site_log_reader, site_utils, test
from autotest_lib.client.bin.chromeos_constants import CLEANUP_LOGS_PAUSED_FILE
from autotest_lib.client.common_lib import error, utils

class LogRotationPauser(object):
    """
    Class to control when logs are rotated from either server or client.

    Assumes all setting of CLEANUP_LOGS_PAUSED_FILE is done by this class
    and that all calls to begin and end are properly
    nested.  For instance, [ a.begin(), b.begin(), b.end(), a.end() ] is
    supported, but [ a.begin(), b.begin(), a.end(), b.end() ]  is not.
    We do support redundant calls to the same class, such as
    [ a.begin(), a.begin(), a.end() ].
    """
    def __init__(self, host=None):
        self._host = host
        self._begun = False
        self._is_nested = True


    def _run(self, command, *args, **dargs):
        if self._host:
            return self._host.run(command, *args, **dargs).exit_status
        else:
            return utils.system(command, *args, **dargs)


    def begin(self):
        """Make sure that log rotation is disabled."""
        if self._begun:
            return
        self._is_nested = (self._run(('[ -r %s ]' %
                                      CLEANUP_LOGS_PAUSED_FILE),
                                     ignore_status=True) == 0)
        if self._is_nested:
            logging.info('File %s was already present' %
                         CLEANUP_LOGS_PAUSED_FILE)
        else:
            self._run('touch ' + CLEANUP_LOGS_PAUSED_FILE)
        self._begun = True


    def end(self):
        assert self._begun
        if not self._is_nested:
            self._run('rm -f ' + CLEANUP_LOGS_PAUSED_FILE)
        else:
            logging.info('Leaving existing %s file' % CLEANUP_LOGS_PAUSED_FILE)
        self._begun = False
