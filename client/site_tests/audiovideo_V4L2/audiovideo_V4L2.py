# Copyright (c) 2010 The Chromium OS Authors. All rights reserved.
# Use of this source code is governed by a BSD-style license that can be
# found in the LICENSE file.

import glob, logging, os, re, time

from autotest_lib.client.bin import test
from autotest_lib.client.common_lib import error, utils

class audiovideo_V4L2(test.test):
    version = 1

    def setup(self):
        # TODO(jiesun): make binary here when cross compile issue is resolved.
        os.chdir(self.srcdir)
        utils.system('make clean')
        utils.system('make')

    def run_once(self):
        # TODO(jiesun): figure out a way to identify primary V4L2 device(s):
        # probably by using the major / minor device id of ( 81, 0 ).
        for device in glob.glob('/dev/video*'):
            self.run_v4l2_unittests(device)
            self.run_v4l2_capture_tests(device)


    def run_v4l2_unittests(self, device):
        self.executable = os.path.join(self.bindir, 'media_v4l2_unittest')
        cmd = '%s --device=%s' % (self.executable, device)
        logging.info("Running %s" % cmd)
        self.info = utils.system_output(cmd, retain_output=True)
        # TODO(jiesun): we had print a lot of information here.
        # need to know what features are mandatory,
        # such buffer i/o methods, supported resolution, supported control,
        # minimum stream i/o buffers requirement, pixel formats.


    def run_v4l2_capture_tests(self, device):
        self.executable = os.path.join(self.bindir, 'media_v4l2_test')

        # if the device claims to support read i/o.
        if re.search('support read', self.info):
            cmd = '%s --device=%s --read' % (self.executable, device)
            logging.info("Running %s" % cmd)
            stdout = utils.system_output(cmd, retain_output=True)

        # if the device claims to support stream i/o.
        # this could mean either mmap stream i/o or user pointer stream i/o.
        # we will try this in turn.
        stream_okay = False;
        if re.search('support streaming i/o', self.info):
            try:
                cmd = ('%s --device=%s --mmap'
                        % (self.executable, device))
                logging.info("Running %s" % cmd)
                stdout = utils.system_output(cmd, retain_output=True)
            except:
                pass
            else:
                stream_okay = True;

            try:
                cmd = ('%s --device=%s --userp'
                        % (self.executable, device))
                logging.info("Running %s" % cmd)
                stdout = utils.system_output(cmd, retain_output=True)
            except:
                pass
            else:
                stream_okay = True;

            if not stream_okay :
                raise error.TestFail('stream i/o failed!')

        # TODO(jiesun): test minimum buffers requirements.
        # we do not know the requirement for now from different clients.
        cmd = '%s --device=%s --buffers=10' % (self.executable, device)
        logging.info("Running %s" % cmd)
        stdout = utils.system_output(cmd, retain_output=True)

        # TODO(jiesun): test with different mandatory resultions that
        # the capture device must support without scaling by ourselves.
        cmd = ('%s --device=%s --width=320 --height=240'
               % (self.executable, device))
        logging.info("Running %s" % cmd)
        stdout = utils.system_output(cmd, retain_output=True)

        cmd = ('%s --device=%s --width=352 --height=288'
               % (self.executable, device))
        logging.info("Running %s" % cmd)
        stdout = utils.system_output(cmd, retain_output=True)

        cmd = ('%s --device=%s --width=176 --height=144'
               % (self.executable, device))
        logging.info("Running %s" % cmd)
        stdout = utils.system_output(cmd, retain_output=True)

        # TODO(jiesun): test with different pixel format that we supported.
        """
        cmd = '%s --device=%s --pixel-format=YUYV' % (self.executable, device)
        logging.info("Running %s" % cmd)
        stdout = utils.system_output(cmd, retain_output=True)

        cmd = '%s --device=%s --pixel-format=NV21' % (self.executable, device)
        logging.info("Running %s" % cmd)
        stdout = utils.system_output(cmd, retain_output=True)
        """

        # TODO(jiesun): test with different framerate we would like to
        # support. from my understanding, this only set maximum fps.
        # not every camera support flexible fps.
        cmd = '%s --device=%s --fps=30' % (self.executable, device)
        logging.info("Running %s" % cmd)
        stdout = utils.system_output(cmd, retain_output=True)

        cmd = '%s --device=%s --fps=15' % (self.executable, device)
        logging.info("Running %s" % cmd)
        stdout = utils.system_output(cmd, retain_output=True)

        cmd = '%s --device=%s --fps=10' % (self.executable, device)
        logging.info("Running %s" % cmd)
        stdout = utils.system_output(cmd, retain_output=True)

        # TODO(jiesun): should we display the result for a visual inspection?
        # maybe this is not used in AutoTest.
        cmd = '%s --device=%s --display' % (self.executable, device)
        logging.info("Running %s" % cmd)
        stdout = utils.system_output(cmd, retain_output=True)

