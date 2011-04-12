# Copyright (c) 2010 The Chromium OS Authors. All rights reserved.
# Use of this source code is governed by a BSD-style license that can be
# found in the LICENSE file.

import logging, os, shutil, platform

from autotest_lib.client.bin import test, utils
from autotest_lib.client.common_lib import error

class realtimecomm_GTalkunittest(test.test):
    version = 1
    unittests = [
        'base_unittest',
        'browserplugin_unittest',
        'call_unittest',
        'flash_unittest',
        'flute_unittest',
        'media_unittest',
        'p2p_unittest',
        'sound_unittest',
        'tunnel_unittest',
        'xmllite_unittest',
        'xmpp_unittest',
    ]

    # On ARM, skip:
    #  call_unittest (doesn't build)
    #  media_unittest  (doesn't build)
    #  flute_unittest (doesn't build)
    arm_unittests = [
        'base_unittest',
        'browserplugin_unittest',
        'flash_unittest',
        'p2p_unittest',
        'sound_unittest',
        'tunnel_unittest',
        'xmllite_unittest',
        'xmpp_unittest',
    ]

    def run_once(self):
        # Stop Google Talk Plugin.
        utils.run('pkill GoogleTalkPlugin', ignore_status=True)

        # Setup as appropriate.
        talk_path = os.path.join(self.autodir, 'talk')
        shutil.rmtree(talk_path, ignore_errors=True)
        shutil.copytree(os.path.join(self.bindir, 'talk'), talk_path)
        utils.run('chown chronos %s -R' % talk_path)
        utils.run(
            'chown chronos /tmp/.google-talk-plugin-theuser.lock.testlock',
            ignore_status=True)

        if "arm" in platform.machine().lower():
          unit_tests_to_run = self.arm_unittests
        else:
          unit_tests_to_run = self.unittests

        # Run all unittests.
        for test_exe in unit_tests_to_run:
            if not os.path.exists(os.path.join(talk_path, test_exe)):
                raise error.TestFail('Missing test binary %s. Make sure gtalk '
                                     'has been emerged.' % test_exe)
            # The unittest has to be run in 'talk' folder.
            test_cmd = "cd %s && su chronos -c \'./%s\'" %  (talk_path,
                                                             test_exe)
            self.__run_one_test(test_cmd)

        # Clean up.
        shutil.rmtree(talk_path)


    def __run_one_test(self, test_cmd):
        logging.info('Running %s' % test_cmd)
        result = utils.run(test_cmd)
        if '[  FAILED  ]' in result.stdout:
            raise error.TestFail(result.stdout)
        logging.info('%s passed.' % test_cmd)
