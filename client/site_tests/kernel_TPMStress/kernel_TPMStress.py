# Copyright (c) 2011 The Chromium OS Authors. All rights reserved.
# Use of this source code is governed by a BSD-style license that can be
# found in the LICENSE file.

import logging, os
from autotest_lib.client.bin import test, utils
from autotest_lib.client.common_lib import error

class kernel_TPMStress(test.test):
  version = 1

  def run_once(self):

    # On a Mario, running the test with 1000 iterations takes 89 seconds, and
    # with 2000 iterations 163 seconds, i.e. the incremental time for 1
    # iteration is 74ms.

    n_iterations = 3000
    iteration = 0

    try:
      utils.system("stop tcsd")

      for iteration in range(1, n_iterations + 1):
        utils.system("tpmc getpf")

    except:
      raise error.TestError("TPM communication error at iteration %d of %d" %
                            (iteration, n_iterations))

    finally:
      utils.system("start tcsd")
