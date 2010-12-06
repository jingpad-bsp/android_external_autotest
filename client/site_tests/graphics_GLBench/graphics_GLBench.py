# Copyright (c) 2010 The Chromium OS Authors. All rights reserved.
# Use of this source code is governed by a BSD-style license that can be
# found in the LICENSE file.

import logging
import os
import re
import pprint

from autotest_lib.client.bin import test
from autotest_lib.client.common_lib import error, utils

def md5_file(filename):
    try:
        return utils.system_output('md5sum ' + filename).split()[0]
    except error.CmdError:
        return None


class graphics_GLBench(test.test):
  version = 1
  preserve_srcdir = True

  def setup(self):
      self.job.setup_dep(['glbench'])


  def run_once(self, options=''):
      dep = 'glbench'
      dep_dir = os.path.join(self.autodir, 'deps', dep)
      self.job.install_pkg(dep, 'dep', dep_dir)

      # These tests do not draw anything, they can only be used to check
      # performance.
      no_checksum_tests = set(['mpixels_sec_pixel_read',
                               'mpixels_sec_pixel_read_2',
                               'mpixels_sec_pixel_read_3',
                               'mvtx_sec_attribute_fetch_shader',
                               'mvtx_sec_attribute_fetch_shader_2_attr',
                               'mvtx_sec_attribute_fetch_shader_4_attr',
                               'mvtx_sec_attribute_fetch_shader_8_attr',
                               'us_swap_swap'])

      checksum_table = {}
      checksums_filename = os.path.join(self.autodir,
                                        'deps/glbench/src/checksums')
      # checksums file is a comma separate list of tuples:
      # (board_1, {test1:checksum1, test2:checksum2}),
      # (board_2, {test1:checksum1, test2:checksum2}),
      # etc.
      checksums = eval('dict([' + utils.read_file(checksums_filename) + '])')

      exefile = os.path.join(self.autodir, 'deps/glbench/glbench')

      options += ' -save'
      out_dir = os.path.join(self.autodir, 'deps/glbench/src/out')

      cmd = "X :1 & sleep 1; DISPLAY=:1 %s %s; kill $!" % (exefile, options)
      results = utils.system_output(cmd, retain_output=True).splitlines()

      if results[0].startswith('# board_id: '):
          board_id = results[0].split('board_id:', 1)[1].strip()
          del results[0]
          logging.info("Running on: %s", board_id)
          checksum_table = checksums.get(board_id, {})
      else:
          checksum_table = {}

      keyvals = {}
      failed_tests = {}
      missing_checksum_tests = {}
      for keyval in results:
          if keyval.strip().startswith('#'):
              continue
          key, val = keyval.split(':')
          testname = key.strip()
          test_checksum = md5_file(os.path.join(out_dir, testname))

          if testname in checksum_table:
              if checksum_table[testname] == test_checksum:
                  keyvals[testname] = float(val)
              else:
                  keyvals[testname] = float('nan')
                  failed_tests[testname] = test_checksum
          else:
              keyvals[testname] = float(val)
              if testname not in no_checksum_tests:
                logging.info('No checksum found for test %s', testname)
                missing_checksum_tests[testname] = test_checksum

      self.write_perf_keyval(keyvals)

      if checksum_table:
          if failed_tests or missing_checksum_tests:
              messages = []
              if failed_tests:
                  messages.append("Incorrect checksums for: %s" %
                                  ', '.join(failed_tests))
              if missing_checksum_tests:
                  messages.append("Missing checksums for: %s" %
                                  ', '.join(missing_checksum_tests))
              raise error.TestFail('; '.join(messages))
      else:
          logging.info("Checksums are missing for: %s.", board_id)
          logging.info("Please verify that the output images are correct " +
                       "and append the following to the checksums file:\n" +
                       pprint.pformat((board_id, missing_checksum_tests)) + ',')
          raise error.TestFail("Checksums are missing for: %s." % board_id)
