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
      self.job.setup_dep(['glbench'])


  def run_once(self, options=''):
      dep = 'glbench'
      dep_dir = os.path.join(self.autodir, 'deps', dep)
      self.job.install_pkg(dep, 'dep', dep_dir)

      exefile = os.path.join(self.autodir, 'deps/glbench/glbench')
      cmd = "X :1 & sleep 1; DISPLAY=:1 %s %s; kill $!" % (exefile, options)
      self.results = utils.system_output(cmd, retain_output=True)

      keyvals = {}
      for keyval in self.results.splitlines():
          if keyval.strip().startswith('#'):
              continue
          key, val = keyval.split(':')
          keyvals[key.strip()] = float(val)

      self.write_perf_keyval(keyvals)
