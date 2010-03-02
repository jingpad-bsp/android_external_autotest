# Copyright (c) 2010 The Chromium OS Authors. All rights reserved.
# Use of this source code is governed by a BSD-style license that can be
# found in the LICENSE file.

import logging, os, shutil

from autotest_lib.client.bin import test, utils
from autotest_lib.client.common_lib import error

class realtimecomm_GTalkunittest(test.test):
    version = 1
    # { test_exe : number_of_testcases }
    unittests = {
        'base_unittest'         : '155',
        'call_unittest'         : '2'  ,
        'flute_unittest'        : '146',
        'flutetesting_unittest' : '3'  ,
        'media_unittest'        : '181',
        'p2p_unittest'          : '228',
        'plugin_unittest'       : '10' ,
        'xmllite_unittest'      : '49' ,
        'xmpp_unittest'         : '37' ,
    }

    def run_once(self):
        # Stop Google Talk Plugin
        utils.run('killall GoogleTalkPlugin', ignore_status=True)
 
        # Setup as appropriate
        talk_path = '/home/chronos/talk'
        shutil.rmtree(talk_path, ignore_errors=True)
        shutil.copytree(os.path.join(self.bindir, 'talk'), talk_path)
        utils.run('chown chronos %s -R' % talk_path)
        utils.run('chown chronos \
            /tmp/.google-talk-plugin-theuser.lock.testlock', ignore_status=True)

        # Run all unittests
        for test_exe in self.unittests:
            # TODO(zhurunz): Support ARM once available.
            x86_talk_path = os.path.join(talk_path, 'i686')
            # The unittest has to be run in 'talk' folder 
            test_cmd = "cd %s && su chronos -c \'./%s\'" % \
                (x86_talk_path, test_exe)
            self.__run_one_test(test_cmd, self.unittests[test_exe])

        # Clean up
        shutil.rmtree(talk_path)


    def __run_one_test(self, test_cmd, number_of_testcases):
        logging.info("Running %s" % test_cmd)
        result = utils.run(test_cmd, ignore_status=True)
        if "[  FAILED  ]" in result.stdout:
            raise error.TestFail(result.stdout)
        expected = "[  PASSED  ] %s tests." % number_of_testcases
        if not expected in result.stdout:
            raise error.TestFail(result.stdout)
        logging.info("%s passed." % test_cmd)

