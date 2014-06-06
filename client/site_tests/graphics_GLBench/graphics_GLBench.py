# Copyright (c) 2010 The Chromium OS Authors. All rights reserved.
# Use of this source code is governed by a BSD-style license that can be
# found in the LICENSE file.

import logging
import os

from autotest_lib.client.bin import test, utils
from autotest_lib.client.common_lib import error
from autotest_lib.client.cros import perf
from autotest_lib.client.cros import service_stopper

# to run this test manually on a test target
# ssh root@machine
# cd /usr/local/autotest/deps/glbench
# stop ui
# X :1 & sleep 1; DISPLAY=:1 ./glbench [-save [-oudir=<dir>]]
# start ui


class graphics_GLBench(test.test):
  version = 1
  preserve_srcdir = True

  # None-init vars used by cleanup() here, in case setup() fails
  _services = None

  reference_images_file = 'deps/glbench/glbench_reference_images.txt'
  knownbad_images_file = 'deps/glbench/glbench_knownbad_images.txt'

  # TODO(ihf) not sure these are still needed
  # These tests do not draw anything, they can only be used to check
  # performance.
  no_checksum_tests = set([
      'compositing_no_fill',
      'pixel_read',
      'pixel_read_2',
      'pixel_read_3',
      'texture_reuse_luminance_teximage2d_1024',
      'texture_reuse_luminance_teximage2d_128',
      'texture_reuse_luminance_teximage2d_1536',
      'texture_reuse_luminance_teximage2d_2048',
      'texture_reuse_luminance_teximage2d_256',
      'texture_reuse_luminance_teximage2d_32',
      'texture_reuse_luminance_teximage2d_512',
      'texture_reuse_luminance_teximage2d_768',
      'texture_reuse_luminance_texsubimage2d_1024',
      'texture_reuse_luminance_texsubimage2d_128',
      'texture_reuse_luminance_texsubimage2d_1536',
      'texture_reuse_luminance_texsubimage2d_2048',
      'texture_reuse_luminance_texsubimage2d_256',
      'texture_reuse_luminance_texsubimage2d_32',
      'texture_reuse_luminance_texsubimage2d_512',
      'texture_reuse_luminance_texsubimage2d_768',
      'texture_reuse_rgba_teximage2d_1024',
      'texture_reuse_rgba_teximage2d_128',
      'texture_reuse_rgba_teximage2d_1536',
      'texture_reuse_rgba_teximage2d_2048',
      'texture_reuse_rgba_teximage2d_256',
      'texture_reuse_rgba_teximage2d_32',
      'texture_reuse_rgba_teximage2d_512',
      'texture_reuse_rgba_teximage2d_768',
      'texture_reuse_rgba_texsubimage2d_1024',
      'texture_reuse_rgba_texsubimage2d_128',
      'texture_reuse_rgba_texsubimage2d_1536',
      'texture_reuse_rgba_texsubimage2d_2048',
      'texture_reuse_rgba_texsubimage2d_256',
      'texture_reuse_rgba_texsubimage2d_32',
      'texture_reuse_rgba_texsubimage2d_512',
      'texture_reuse_rgba_texsubimage2d_768',
      'context_glsimple',
      'swap_glsimple', ])

  blacklist = ''

  unit_higher_is_better = {
    'mpixels_sec': True,
    'mtexel_sec': True,
    'mtri_sec': True,
    'mvtx_sec': True,
    'us': False,
    '1280x768_fps': True }

  def setup(self):
    self.job.setup_dep(['glbench'])

  def initialize(self):
    self._services = service_stopper.ServiceStopper(['ui'])

  def cleanup(self):
    if self._services:
      self._services.restore_services()

  def report_temperature(self, keyname):
    temperature = utils.get_temperature_input_max()
    logging.info('%s = %f degree Celsius', keyname, temperature)
    self.output_perf_value(description=keyname, value=temperature,
                           units='Celsius', higher_is_better=False)

  def report_temperature_critical(self, keyname):
    temperature = utils.get_temperature_critical()
    logging.info('%s = %f degree Celsius', keyname, temperature)
    self.output_perf_value(description=keyname, value=temperature,
                           units='Celsius', higher_is_better=False)

  def run_once(self, options='', hasty=False):
    dep = 'glbench'
    dep_dir = os.path.join(self.autodir, 'deps', dep)
    self.job.install_pkg(dep, 'dep', dep_dir)

    options += self.blacklist

    # Run the test, saving is optional and helps with debugging
    # and reference image management. If unknown images are
    # encountered one can take them from the outdir and copy
    # them (after verification) into the reference image dir.
    exefile = os.path.join(self.autodir, 'deps/glbench/glbench')
    outdir = self.outputdir
    options += ' -save -outdir=' + outdir
    # Using the -hasty option we run only a subset of tests without waiting
    # for thermals to normalize. Test should complete in 15-20 seconds.
    if hasty:
      options += ' -hasty'
    cmd = '%s %s' % (exefile, options)

    # If UI is running, we must stop it and restore later.
    self._services.stop_services()

    # Just sending SIGTERM to X is not enough; we must wait for it to
    # really die before we start a new X server (ie start ui).
    # The term_process function of /sbin/killers makes sure that all X
    # process are really dead before returning; this is what stop ui uses.
    kill_cmd = '. /sbin/killers; term_process "^X$"'
    cmd = 'X :1 vt1 & sleep 1; chvt 1 && DISPLAY=:1 %s; %s' % (cmd, kill_cmd)
    summary = None
    if hasty:
      # On BVT the test will not monitor thermals so we will not verify its
      # correct status using PerControl
      summary = utils.run(cmd,
                          stdout_tee=utils.TEE_TO_LOGS,
                          stderr_tee=utils.TEE_TO_LOGS).stdout
    else:
      self.report_temperature_critical('temperature_critical')
      self.report_temperature('temperature_1_start')
      # Wrap the test run inside of a PerfControl instance to make machine
      # behavior more consistent.
      with perf.PerfControl() as pc:
        if not pc.verify_is_valid():
          raise error.TestError(pc.get_error_reason())
        self.report_temperature('temperature_2_before_test')

        # Run the test. If it gets the CPU too hot pc should notice.
        summary = utils.run(cmd,
                            stdout_tee=utils.TEE_TO_LOGS,
                            stderr_tee=utils.TEE_TO_LOGS).stdout
        if not pc.verify_is_valid():
          raise error.TestError(pc.get_error_reason())

    # Write a copy of stdout to help debug failures.
    results_path = os.path.join(self.outputdir, 'summary.txt')
    f = open(results_path, 'w+')
    f.write('# ---------------------------------------------------\n')
    f.write('# [' + cmd + ']\n')
    f.write(summary)
    f.write('\n# -------------------------------------------------\n')
    f.write('# [graphics_GLBench.py postprocessing]\n')

    # Analyze the output. Sample:
    ## board_id: NVIDIA Corporation - Quadro FX 380/PCI/SSE2
    ## Running: ../glbench -save -outdir=img
    #swap_swap = 221.36 us [swap_swap.pixmd5-20dbc...f9c700d2f.png]
    results = summary.splitlines()
    if not results:
      f.close()
      raise error.TestFail('No output from test. Check /tmp/' +
                           'run_remote_tests.../graphics_GLBench/summary.txt' +
                           ' for details.')

    # initialize reference images index for lookup
    reference_imagenames = os.path.join(self.autodir,
                                        self.reference_images_file)
    g = open(reference_imagenames, 'r')
    reference_imagenames = g.read()
    g.close()
    knownbad_imagenames = os.path.join(self.autodir,
                                       self.knownbad_images_file)
    g = open(knownbad_imagenames, 'r')
    knownbad_imagenames = g.read()
    g.close()

    # Check if we saw GLBench end as expected (without crashing).
    test_ended_normal = False
    for line in results:
      if line.strip().startswith('@TEST_END'):
        test_ended_normal = True

    # Analyze individual test results in summary.
    keyvals = {}
    failed_tests = {}
    for line in results:
      if not line.strip().startswith('@RESULT: '):
        continue
      keyval, remainder = line[9:].split('[')
      key, val = keyval.split('=')
      testname = key.strip()
      score, unit = val.split()
      testrating = float(score)
      imagefile = remainder.split(']')[0]

      higher = self.unit_higher_is_better.get(unit)
      if higher is None:
        raise error.TestFail('Unknown test unit "%s" for %s' % (unit, testname))

      if not hasty:
        # prepend unit to test name to maintain backwards compatibility with
        # existing per data
        perf_value_name = '%s_%s' % (unit, testname)
        self.output_perf_value(description=perf_value_name, value=testrating,
                               units=unit, higher_is_better=higher)

      # classify result image
      if testrating == -1.0:
        # tests that generate GL Errors
        glerror = imagefile.split('=')[1]
        f.write('# GLError ' + glerror + ' during test (perf set to -3.0)\n')
        keyvals[testname] = -3.0
      elif testrating == 0.0:
        # tests for which glbench does not generate a meaningful perf score
        f.write('# No score for test\n')
        keyvals[testname] = 0.0
      elif imagefile in knownbad_imagenames:
        # we already know the image looks bad and have filed a bug
        # so don't throw an exception and remind there is a problem
        keyvals[testname] = -1.0
        f.write('# knownbad [' + imagefile + '] (setting perf as -1.0)\n')
      elif imagefile in reference_imagenames:
        # known good reference images
        keyvals[testname] = testrating
      elif imagefile == 'none':
        # tests that do not write images
        keyvals[testname] = testrating
      elif testname in self.no_checksum_tests:
        # TODO(ihf) these really should not write any images
        keyvals[testname] = testrating
      else:
        # completely unknown images
        keyvals[testname] = -2.0
        failed_tests[testname] = imagefile
        f.write('# unknown [' + imagefile + '] (setting perf as -2.0)\n')
    f.close()
    if not hasty:
      self.report_temperature('temperature_3_after_test')
      self.write_perf_keyval(keyvals)

    # Raise exception if images don't match.
    if failed_tests:
      logging.info('Some images are not matching their reference in %s.',
                   self.reference_images_file)
      logging.info('Please verify that the output images are correct '
                   'and if so copy them to the reference directory.')
      raise error.TestFail('Some images are not matching their '
                           'references. Check /tmp/'
                           'run_remote_tests.../graphics_GLBench/summary.txt'
                           ' for details.')

    if not test_ended_normal:
      raise error.TestFail('No end marker. Presumed crash/missing images.')
