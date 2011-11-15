#!/usr/bin/python
# Copyright (c) 2012 The Chromium OS Authors. All rights reserved.
# Use of this source code is governed by a BSD-style license that can be
# found in the LICENSE file.

import logging
import os

from autotest_lib.client.bin import utils
from autotest_lib.client.common_lib import error

LD_LIBRARY_PATH = 'LD_LIBRARY_PATH'

class AudioHelper(object):
    '''
    A helper class contains audio related utility functions.
    '''
    def __init__(self, test):
        self._test = test

    def setup_deps(self, deps):
        '''
        Sets up audio related dependencies.
        '''
        for dep in deps:
            if dep == 'test_tones':
                dep_dir = os.path.join(self._test.autodir, 'deps', dep)
                self._test.job.install_pkg(dep, 'dep', dep_dir)
                self.test_tones_path = os.path.join(dep_dir, 'src', dep)
            elif dep == 'audioloop':
                dep_dir = os.path.join(self._test.autodir, 'deps', dep)
                self._test.job.install_pkg(dep, 'dep', dep_dir)
                self.audioloop_path = os.path.join(dep_dir, 'src',
                        'looptest')
            elif dep == 'sox':
                dep_dir = os.path.join(self._test.autodir, 'deps', dep)
                self._test.job.install_pkg(dep, 'dep', dep_dir)
                self.sox_path = os.path.join(dep_dir, 'bin', dep)
                self.sox_lib_path = os.path.join(dep_dir, 'lib')
                if os.environ.has_key(LD_LIBRARY_PATH):
                    paths = os.environ[LD_LIBRARY_PATH].split(':')
                    if not self.sox_lib_path in paths:
                        paths.append(self.sox_lib_path)
                        os.environ[LD_LIBRARY_PATH] = ':'.join(paths)
                else:
                    os.environ[LD_LIBRARY_PATH] = self.sox_lib_path

    def cleanup_deps(self, deps):
        '''
        Cleans up environments which has been setup for dependencies.
        '''
        for dep in deps:
            if dep == 'sox':
                if (os.environ.has_key(LD_LIBRARY_PATH)
                        and hasattr(self, 'sox_lib_path')):
                    paths = filter(lambda x: x != self.sox_lib_path,
                            os.environ[LD_LIBRARY_PATH].split(':'))
                    os.environ[LD_LIBRARY_PATH] = ':'.join(paths)

    def set_mixer_controls(self, mixer_settings={}, card='0'):
        '''
        Sets all mixer controls listed in the mixer settings on card.
        '''
        logging.info('Setting mixer control values on %s' % card)
        for item in mixer_settings:
            logging.info('Setting %s to %s on card %s' %
                         (item['name'], item['value'], card))
            cmd = 'amixer -c %s cset name=%s %s'
            cmd = cmd % (card, item['name'], item['value'])
            try:
                utils.system(cmd)
            except error.CmdError:
                # A card is allowed not to support all the controls, so don't
                # fail the test here if we get an error.
                logging.info('amixer command failed: %s' % cmd)
