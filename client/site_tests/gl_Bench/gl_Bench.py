# Copyright (c) 2010 The Chromium OS Authors. All rights reserved.
# Use of this source code is governed by a BSD-style license that can be
# found in the LICENSE file.

import os

from autotest_lib.client.bin import test
from autotest_lib.client.common_lib import utils

class gl_Bench(test.test):
  version = 1
  preserve_srcdir = True

  def setup(self):
    os.chdir(self.srcdir)
    utils.system('make clean')
    utils.system('make')


  def run_once(self, options=''):
    exefile = os.path.join(self.bindir, 'gl_Bench')
    cmd = "X :1 & sleep 1; DISPLAY=:1 %s %s; kill $!" % (exefile, options)
    self.results = utils.system_output(cmd, retain_output=True)

    for keyval in self.results.splitlines():
      if keyval.strip().startswith('#'):
	continue
      key, val = keyval.split(':')
      self.write_perf_keyval({key.strip(): val.strip()})
