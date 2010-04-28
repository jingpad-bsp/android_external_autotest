# Copyright (c) 2010 The Chromium OS Authors. All rights reserved.
# Use of this source code is governed by a BSD-style license that can be
# found in the LICENSE file.


import logging, re, time
from autotest_lib.client.bin import test, utils
from autotest_lib.client.common_lib import error, site_ui


class desktopui_FlashSanityCheck(test.test):
    version = 1


    def run_once(self, time_to_wait=25):
        if utils.get_arch() != 'i386':
            raise error.TestNAError('Only supported on x86')

        # take a snapshot from /var/log/messages.
        msg_linecount = utils.system_output('wc -l /var/log/messages')
        logging.debug(msg_linecount)

        # open browser to youtube.com.
        session = site_ui.ChromeSession('http://www.youtube.com')
        # wait some time till the webpage got fully loaded.
        time.sleep(time_to_wait)
        session.close()
        # Question: do we need to test with other popular flash website?

        # take another snapshot from /var/log/message.
        # there should be no messages.
        new_msg = utils.system_output('tail -n +%s /var/log/messages' %
                                      msg_linecount.split()[0])

        # any better pattern matching?
        if re.search(r' chrome\[.* segfault at', new_msg):
            # well, there is a crash. sample crash message:
            # 2010-04-21T18:17:21.181068+00:00 localhost kernel: [88602.303508]
            # chrome[2961]: segfault at 6dc08030 ip 00192bcd sp 77d33f14 error 4
            # in libpthread-2.10.1.so[18b000+14000]
            raise error.TestFail('Browser crashed during test.\nMessage '
                                 'from /var/log/messages:\n%s' % new_msg)
