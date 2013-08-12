# Copyright (c) 2010 The Chromium OS Authors. All rights reserved.
# Use of this source code is governed by a BSD-style license that can be
# found in the LICENSE file.

import logging
import os
import pprint
import urllib2

from autotest_lib.client.bin import test, utils
from autotest_lib.client.common_lib import error, utils

# to run this test manually on a test target
# ssh root@machine
# cd /usr/local/autotest/deps/glbench
# stop ui
# X :1 & sleep 1; DISPLAY=:1 ./glbench [-save [-oudir=<dir>]]
# start ui


def ReferenceImageExists(images_file, images_url, imagename):
  found = False
  # check imagename in index file first
  if imagename in images_file:
    return True
  # check if image can be found on web server
  url = images_url + imagename
  try:
    urllib2.urlopen(urllib2.Request(url))
    found = True
  except:
    found = False
  return found


class graphics_GLBench(test.test):
  version = 1
  preserve_srcdir = True

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

  def run_once(self, options=''):
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
    need_restart_ui = False
    status_output = utils.system_output('initctl status ui')
    # If chrome is running, result will be similar to:
    #   ui start/running, process 11895
    logging.info('initctl status ui returns: %s', status_output)
    need_restart_ui = status_output.startswith('ui start')

    cmd = 'X :1 & sleep 1; DISPLAY=:1 %s; kill $!' % cmd

    if need_restart_ui:
      utils.system('initctl stop ui', ignore_status=True)

    try:
      summary = utils.system_output(cmd, retain_output=True)
    finally:
      if need_restart_ui:
        utils.system('initctl start ui')

    # write a copy of stdout to help debug failures
    results_path = os.path.join(self.outputdir, 'summary.txt')
    f = open(results_path, 'w+')
    f.write('# need ui restart: %s\n' % need_restart_ui)
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
      # TODO(ihf) move here the check for valid test rating numbers

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
    f.close()
    self.write_perf_keyval(keyvals)

    # raise exception
    if failed_tests:
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
