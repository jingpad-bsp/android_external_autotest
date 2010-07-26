# Copyright (c) 2009 The Chromium OS Authors. All rights reserved.
# Use of this source code is governed by a BSD-style license that can be
# found in the LICENSE file.

__author__ = 'kobic@codeaurora.org (Kobi Cohen-Arazi)'

import os
import datetime
import logging
import re
import utils
from autotest_lib.client.bin import test
from autotest_lib.client.common_lib import error

class platform_Rootdev(test.test):
    version = 1

    def run_once(self):

        cpuType = utils.get_cpu_arch()
        logging.debug("cpu type is %s" % cpuType)

        # test return values
        result = utils.system("rootdev")
        logging.debug("Rootdev test res: %d", result)
        if (result != 0):
            raise error.TestFail("Rootdev failed")
        result = utils.system("rootdev -d")
        logging.debug("Rootdev test -d switch res: %d", result)
        if (result != 0):
            raise error.TestFail("Rootdev failed -d")

        # test content
        text = utils.system_output("rootdev 2>&1")
        text=text.strip()
        logging.debug("Rootdev txt is *%s*", text)
        if(cpuType == "arm"):
            if(text != "/dev/mmcblk0p3" and text != "/dev/mmcblk1p3"):
                raise error.TestFail(
                    "Rootdev arm failed != /dev/mmcblk0p3 and != mmcblk1p3")
        else:
            if(text != "/dev/sda3" and text != "/dev/sdb3"):
                raise error.TestFail(
                    "Rootdev x86 failed != /dev/sda3 and != sdb3")

        # test with -d Results should be without the partition device number
        text = utils.system_output("rootdev -d 2>&1")
        text = text.strip()
        logging.debug("Rootdev -d txt is *%s*", text)
        if(cpuType == "arm"):
            if(text != "/dev/mmcblk0" and text != "/dev/mmcblk1"):
                raise error.TestFail(
                    "Rootdev arm failed != /dev/mmcblk0 and != mmcblk1")
        else:
            if(text != "/dev/sda" and text != "/dev/sdb"):
                raise error.TestFail(
                    "Rootdev x86 failed != /dev/sda and != sdb")


