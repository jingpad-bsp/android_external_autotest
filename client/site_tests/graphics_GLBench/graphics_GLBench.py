# Copyright (c) 2010 The Chromium OS Authors. All rights reserved.
# Use of this source code is governed by a BSD-style license that can be
# found in the LICENSE file.

import logging
import os
import time
import pprint
import urllib2
import httplib

from autotest_lib.client.bin import test, utils
from autotest_lib.client.common_lib import error
from autotest_lib.client.cros import service_stopper

# to run this test manually on a test target
# ssh root@machine
# cd /usr/local/autotest/deps/glbench
# stop ui
# X :1 & sleep 1; DISPLAY=:1 ./glbench [-save [-oudir=<dir>]]
# start ui


# Keep track of hosts that result in any errors other than HTTPError 404 (url
# not found).  A 404 error is expected (and timely).  Any other error means
# that the access timed out.  Avoid any subsequent attempt to access that "bad"
# host, to avoid accumulation of many timeouts.
bad_host_cache = set()

def ReferenceImageExists(images_file, images_url, imagename):
  found = False
  # check imagename in index file first
  if imagename in images_file:
    return True
  # check if image can be found on web server
  url = images_url + imagename
  host = urllib2.urlparse.urlparse(url).netloc
  if host in bad_host_cache:
    logging.warning('skipping cached unreachable host %s' % host)
    return False
  try:
    urllib2.urlopen(urllib2.Request(url))
    found = True
  except (urllib2.HTTPError, urllib2.URLError, httplib.HTTPException) as e:
    found = False
    if not (isinstance(e, urllib2.HTTPError) and e.getcode() == 404):
      bad_host_cache.add(host)
      logging.warning('cached unreachable host %s' % host)
  return found


class graphics_GLBench(test.test):
  version = 1
  preserve_srcdir = True

  # None-init vars used by cleanup() here, in case setup() fails
  _services = None

  reference_images_file = 'deps/glbench/glbench_reference_images.txt'
  knownbad_images_file = 'deps/glbench/glbench_knownbad_images.txt'

  reference_images_url = ('http://commondatastorage.googleapis.com/'
                          'chromeos-localmirror/distfiles/'
                          'glbench_reference_images/')
  knownbad_images_url = ('http://commondatastorage.googleapis.com/'
                         'chromeos-localmirror/distfiles/'
                         'glbench_knownbad_images/')

  # TODO(ihf) not sure these are still needed
  # These tests do not draw anything, they can only be used to check
  # performance.
  no_checksum_tests = set(['1280x768_fps_no_fill_compositing',
                           'mpixels_sec_pixel_read',
                           'mpixels_sec_pixel_read_2',
                           'mpixels_sec_pixel_read_3',
                           'mtexel_sec_texture_reuse_teximage2d_1024',
                           'mtexel_sec_texture_reuse_teximage2d_128',
                           'mtexel_sec_texture_reuse_teximage2d_1536',
                           'mtexel_sec_texture_reuse_teximage2d_2048',
                           'mtexel_sec_texture_reuse_teximage2d_256',
                           'mtexel_sec_texture_reuse_teximage2d_32',
                           'mtexel_sec_texture_reuse_teximage2d_512',
                           'mtexel_sec_texture_reuse_teximage2d_768',
                           'mtexel_sec_texture_reuse_texsubimage2d_1024',
                           'mtexel_sec_texture_reuse_texsubimage2d_128',
                           'mtexel_sec_texture_reuse_texsubimage2d_1536',
                           'mtexel_sec_texture_reuse_texsubimage2d_2048',
                           'mtexel_sec_texture_reuse_texsubimage2d_256',
                           'mtexel_sec_texture_reuse_texsubimage2d_32',
                           'mtexel_sec_texture_reuse_texsubimage2d_512',
                           'mtexel_sec_texture_reuse_texsubimage2d_768',
                           'mtexel_sec_texture_upload_teximage2d_1024',
                           'mtexel_sec_texture_upload_teximage2d_128',
                           'mtexel_sec_texture_upload_teximage2d_1536',
                           'mtexel_sec_texture_upload_teximage2d_2048',
                           'mtexel_sec_texture_upload_teximage2d_256',
                           'mtexel_sec_texture_upload_teximage2d_32',
                           'mtexel_sec_texture_upload_teximage2d_512',
                           'mtexel_sec_texture_upload_teximage2d_768',
                           'mtexel_sec_texture_upload_texsubimage2d_1024',
                           'mtexel_sec_texture_upload_texsubimage2d_128',
                           'mtexel_sec_texture_upload_texsubimage2d_1536',
                           'mtexel_sec_texture_upload_texsubimage2d_2048',
                           'mtexel_sec_texture_upload_texsubimage2d_256',
                           'mtexel_sec_texture_upload_texsubimage2d_32',
                           'mtexel_sec_texture_upload_texsubimage2d_512',
                           'mtexel_sec_texture_upload_texsubimage2d_768',
                           'mvtx_sec_attribute_fetch_shader',
                           'mvtx_sec_attribute_fetch_shader_2_attr',
                           'mvtx_sec_attribute_fetch_shader_4_attr',
                           'mvtx_sec_attribute_fetch_shader_8_attr',
                           'us_context_glsimple',
                           'us_context_nogl',
                           'us_swap_glsimple',
                           'us_swap_nogl', ])

  blacklist = ''

  def setup(self):
    self.job.setup_dep(['glbench'])

  def initialize(self):
    self._services = service_stopper.ServiceStopper(['ui'])

  def cleanup(self):
    if self._services:
      self._services.restore_services()

  def report_temperature(self, keyname):
    try:
      f = open('/sys/class/hwmon/hwmon0/temp1_input')
      temperature = float(f.readline()) * 0.001
    except Exception:
      temperature = - 1000.0
    logging.info('%s = %f degree Celsius', keyname, temperature)
    self.output_perf_value(description=keyname, value=temperature,
                           units='Celsius', higher_is_better=False)

  def report_temperature_critical(self):
    keyname = 'temperature_critical'
    try:
      f = open('/sys/class/hwmon/hwmon0/temp1_crit')
      temperature = float(f.readline()) * 0.001
    except Exception:
      temperature = - 1000.0
    logging.info('%s = %f degree Celsius', keyname, temperature)
    self.output_perf_value(description=keyname, value=temperature,
                           units='Celsius', higher_is_better=False)

  def get_unit_from_test(self, testname):
    if testname.startswith('mpixels_sec_'):
      return ('mpixels_sec', True)
    if testname.startswith('mtexel_sec_'):
      return ('mtexel_sec', True)
    if testname.startswith('mtri_sec_'):
      return ('mtri_sec', True)
    if testname.startswith('mvtx_sec_'):
      return ('mvtx_sec', True)
    if testname.startswith('us_'):
      return ('us', False)
    if testname.startswith('1280x768_fps_'):
      return ('fps', True)
    raise error.TestFail('Unknown test unit in ' + testname)

  def run_once(self, options='', raise_error_on_checksum=True):
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

    cmd = '%s %s' % (exefile, options)

    # If UI is running, we must stop it and restore later.
    self._services.stop_services()

    # Just sending SIGTERM to X is not enough; we must wait for it to
    # really die before we start a new X server (ie start ui).
    # The term_process function of /sbin/killers makes sure that all X
    # process are really dead before returning; this is what stop ui uses.
    kill_cmd = '. /sbin/killers; term_process "^X$"'
    cmd = 'X :1 vt1 & sleep 1; chvt 1 && DISPLAY=:1 %s; %s' % (cmd, kill_cmd)

    if not utils.wait_for_cool_idle_perf_machine():
      raise error.TestFail('Could not get cool/idle machine for test.')

    # TODO(ihf): Remove this sleep once this test is guaranteed to run on a
    # cold machine.
    self.report_temperature_critical()
    self.report_temperature('temperature_1_start')
    logging.info('Sleeping machine for one minute to physically cool down.')
    time.sleep(60)
    self.report_temperature('temperature_2_before_test')

    summary = utils.system_output(cmd, retain_output=True)

    # write a copy of stdout to help debug failures
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
    #us_swap_swap = 221.36 [us_swap_swap.pixmd5-20dbc...f9c700d2f.png]
    results = summary.splitlines()
    if not results:
      f.close()
      raise error.TestFail('No output from test. Check /tmp/' +
                           'run_remote_tests.../graphics_GLBench/summary.txt' +
                           ' for details.')
    # analyze summary header
    if results[0].startswith('# board_id: '):
      board_id = results[0].split('board_id:', 1)[1].strip()
      del results[0]

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

    # analyze individual test results in summary
    keyvals = {}
    failed_tests = {}
    for line in results:
      if line.strip().startswith('#'):
        continue
      keyval, remainder = line.split('[')
      key, val = keyval.split('=')
      testname = key.strip()
      testrating = float(val)
      imagefile = remainder.split(']')[0]
      unit, higher = self.get_unit_from_test(testname)
      logging.info('%s %s %d', testname, unit, higher)
      self.output_perf_value(description=testname, value=testrating,
                             units=unit, higher_is_better=higher)

      # classify result image
      if ReferenceImageExists(knownbad_imagenames,
                              self.knownbad_images_url,
                              imagefile):
        # we already know the image looks bad and have filed a bug
        # so don't throw an exception and remind there is a problem
        keyvals[testname] = -1.0
        f.write('# knownbad [' + imagefile + '] (setting perf as -1.0)\n')
      else:
        if ReferenceImageExists(reference_imagenames,
                                self.reference_images_url,
                                imagefile):
          # known good reference images
          keyvals[testname] = testrating
        else:
          if testname in self.no_checksum_tests:
            # TODO(ihf) these really should not write any images
            keyvals[testname] = testrating
          else:
            # completely unknown images
            keyvals[testname] = -2.0
            failed_tests[testname] = imagefile
            f.write('# unknown [' + imagefile + '] (setting perf as -2.0)\n')

    self.report_temperature('temperature_3_after_test')
    f.close()
    self.write_perf_keyval(keyvals)

    # raise exception
    if failed_tests and raise_error_on_checksum:
      logging.info('GLBench board_id: %s', board_id)
      logging.info('Some images are not matching their reference in %s or %s.',
                   self.reference_images_file,
                   self.reference_images_url)
      logging.info('Please verify that the output images are correct '
                   'and if so copy them to the reference directory:\n' +
                   pprint.pformat((board_id, failed_tests)) + ',')
      raise error.TestFail('Some images are not matching their '
                           'references. Check /tmp/'
                           'run_remote_tests.../graphics_GLBench/summary.txt'
                           ' for details.')
