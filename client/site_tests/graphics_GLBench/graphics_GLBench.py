# Copyright (c) 2010 The Chromium OS Authors. All rights reserved.
# Use of this source code is governed by a BSD-style license that can be
# found in the LICENSE file.

import logging
import os
import re

from autotest_lib.client.bin import test
from autotest_lib.client.common_lib import error, site_ui, utils

def md5_file(filename):
  return utils.system_output('md5sum ' + filename).split()[0]


class graphics_GLBench(test.test):
  version = 1
  preserve_srcdir = True

  def setup(self):
      self.job.setup_dep(['glbench'])


  def run_once(self, options=''):
      dep = 'glbench'
      dep_dir = os.path.join(self.autodir, 'deps', dep)
      self.job.install_pkg(dep, 'dep', dep_dir)

      checksum_table = {}
      checksums_filename = os.path.join(self.autodir,
                                        'deps/glbench/src/checksums')
      checksums = eval(utils.read_file(checksums_filename))

      exefile = os.path.join(self.autodir, 'deps/glbench/glbench')
      board_id = utils.system_output(site_ui.xcommand(exefile +
          ' -get_board_id')).strip()
      logging.info("Running on: %s", board_id)
      checksum_table = checksums.get(board_id, {})

      if checksum_table:
        options += ' -save'
        out_dir = os.path.join(self.autodir, 'deps/glbench/src/out')
      else:
        raise error.TestFail("No checksums found for this board: %s" % board_id)

      cmd = "X :1 & sleep 1; DISPLAY=:1 %s %s; kill $!" % (exefile, options)
      self.results = utils.system_output(cmd, retain_output=True)

      keyvals = {}
      failed_tests = []
      for keyval in self.results.splitlines():
          if keyval.strip().startswith('#'):
              continue
          key, val = keyval.split(':')
          testname = key.strip()

          if testname in checksum_table:
            if checksum_table[testname] == md5_file(
                os.path.join(out_dir, testname)):
              keyvals[testname] = float(val)
            else:
              keyvals[testname] = float('nan')
              failed_tests.append(testname)
          else:
            logging.info('No checksum found for test %s', testname)
            keyvals[testname] = float(val)

      self.write_perf_keyval(keyvals)
      if failed_tests:
        raise error.TestFail("Incorrect checksums for %s" %
                             ', '.join(failed_tests))
