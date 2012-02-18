# Copyright (c) 2011 The Chromium OS Authors. All rights reserved.
# Use of this source code is governed by a BSD-style license that can be
# found in the LICENSE file.

import copy
import hashlib
import logging
import os

from autotest_lib.client.cros import factory
from autotest_lib.client.bin import utils


def _TryReadFile(path):
    '''
    Returns the contents of a file if it exists, else returns None.
    '''
    if os.path.exists(path):
        return open(path).read()
    else:
        return None


class PluggableConfig(object):
    '''
    A pluggable configuration for a test.  May include, for example,
    frequency ranges to test or device calibration parameters.

    The configuration may be replaced at runtime by reading a file (e.g., from a
    USB stick).
    '''
    def __init__(self, default_config):
        self.default_config = default_config

    def Read(self, config_path=None, timeout=30):
        '''
        Reads and returns the configuration.

        Uses the default configuration if 'config_path' is None.

        Args:
            config_path: (optional) Path to configuration file.
            timeout: Number of seconds to wait for the configuration file.
        '''
        if config_path:
            factory.console.info(
                'Waiting for test configuration file %r...', config_path)
            config_str = utils.poll_for_condition(
                lambda: _TryReadFile(config_path),
                timeout=timeout, desc='Configuration file %r' % config_path)
            factory.console.info('Read test configuration file %r', config_path)
            logging.info('Configuration file %r: MD5=%s; contents="""%s"""',
                         config_path,
                         hashlib.md5(config_str).hexdigest(),
                         config_str)
            return eval(config_str)
        else:
            logging.info('Using default configuration %r', self.default_config)
            # Return a copy, just in case the caller changes it.
            return copy.deepcopy(self.default_config)
