# Copyright (c) 2010 The Chromium OS Authors. All rights reserved.
# Use of this source code is governed by a BSD-style license that can be
# found in the LICENSE file.

import logging, os
from autotest_lib.client.bin import test, utils
from autotest_lib.client.common_lib import error

class kernel_TPMPing(test.test):
  version = 1

  def run_once(self):
    version = utils.system_output("tpm_version")
    if version.find("Version Info") == -1:
      raise error.TestError("Invalid output of tpm_version:\n%s\n" % version)
    else:
      logging.info(version)
