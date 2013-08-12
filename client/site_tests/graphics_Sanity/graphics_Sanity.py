# Copyright (c) 2010 The Chromium OS Authors. All rights reserved.
# Use of this source code is governed by a BSD-style license that can be
# found in the LICENSE file.

import os

from autotest_lib.client.bin import test, utils
from autotest_lib.client.cros import service_stopper

# to run this test manually on a test target
# ssh root@machine
# cd /usr/local/autotest/deps/glbench
# stop ui
# X :0 & sleep 1; DISPLAY=:0 ./windowmanagertest --screenshot1_sec 2 \
#    --screenshot2_sec 1  --cooldown_sec 1 \
#    --screenshot1_cmd "DISPLAY=:0 import -channel RGB -colorspace RGB \
#        -depth 8 -window root screenshot1_generated.png" \
#    --screenshot2_cmd "DISPLAY=:0 import -channel RGB -colorspace RGB \
#        -depth 8 -window root screenshot2_generated.png"
# start ui

class graphics_Sanity(test.test):
    """
    This test is meant to be used as a quick sanity check for GL/GLES.
    """
    version = 1

    # None-init vars used by cleanup() here, in case setup() fails
    _services = None


    def setup(self):
        self.job.setup_dep(['glbench'])


    def initialize(self):
        self._services = service_stopper.ServiceStopper(['ui'])


    def cleanup(self):
        if self._services:
            self._services.restore_services()


    def run_once(self):
        """
        Draws a texture with a soft ellipse twice and captures each image.
        Compares the output fuzzily against reference images.
        """
        dep = 'glbench'
        dep_dir = os.path.join(self.autodir, 'deps', dep)
        self.job.install_pkg(dep, 'dep', dep_dir)

        screenshot1_reference = os.path.join(self.bindir,
                                            "screenshot1_reference.png")
        screenshot1_generated = os.path.join(self.resultsdir,
                                            "screenshot1_generated.png")
        screenshot1_resized = os.path.join(self.resultsdir,
                                            "screenshot1_generated_resized.png")
        screenshot2_reference = os.path.join(self.bindir,
                                            "screenshot2_reference.png")
        screenshot2_generated = os.path.join(self.resultsdir,
                                            "screenshot2_generated.png")
        screenshot2_resized = os.path.join(self.resultsdir,
                                            "screenshot2_generated_resized.png")

        exefile = os.path.join(self.autodir, 'deps/glbench/windowmanagertest')

        # Delay before screenshot: 1 second has caused failures.
        options = ' --screenshot1_sec 2'
        options += ' --screenshot2_sec 1'
        options += ' --cooldown_sec 1'
        # perceptualdiff can handle only 8 bit images.
        options += ' --screenshot1_cmd "DISPLAY=:1 import -channel RGB'
        options += ' -colorspace RGB -depth 8 -window root'
        options += ' %s"' % screenshot1_generated
        options += ' --screenshot2_cmd "DISPLAY=:1 import -channel RGB'
        options += ' -colorspace RGB -depth 8 -window root'
        options += ' %s"' % screenshot2_generated

        cmd = "%s %s" % (exefile, options)
        # Just sending SIGTERM to X is not enough; we must wait for it to
        # really die before we start a new X server (ie start ui).
        # The term_process function of /sbin/killers makes sure that all X
        # process are really dead before returning; this is what stop ui uses.
        kill_cmd = '. /sbin/killers; term_process "^X$"'
        cmd = 'X :1 vt1 & sleep 1; chvt 1 && DISPLAY=:1 %s; %s' % (cmd,
                                                                   kill_cmd)

        # If UI is running, we must stop it and restore later.
        self._services.stop_services()

        utils.system(cmd)

        # convert -resize -depth 8 does not work. But resize honors previously
        # chosen bit depth.
        utils.system("convert -resize '100x100!' %s %s" %
                     (screenshot1_generated, screenshot1_resized))
        utils.system("convert -resize '100x100!' %s %s" %
                     (screenshot2_generated, screenshot2_resized))
        os.remove(screenshot1_generated)
        os.remove(screenshot2_generated)

        utils.system("perceptualdiff -verbose %s %s"
                     % (screenshot1_reference, screenshot1_resized))
        utils.system("perceptualdiff -verbose %s %s"
                     % (screenshot2_reference, screenshot2_resized))
