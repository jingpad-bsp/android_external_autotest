#!/usr/bin/python
# Copyright (c) 2011 The Chromium OS Authors. All rights reserved.
# Use of this source code is governed by a BSD-style license that can be
# found in the LICENSE file.

"""Autotest test routines to use Google Storage based gesture files for test.

The Chrome OS project uses Google Storage to house the many files that will
feed the hardware_Trackpad test.  This library interfaces with Google Storage
for any test that needs to request and retrieve files from this repository
of test files.

EXAMPLE: the following is an example of code that may be added to the
         hardware_Trackpad test to make default gesture files available to the
         test in response to an online, model-dependent query:
...
import cros_gestures_lib
...
    def setup(self):
        gesture_lib = cros_gestures_lib.CrosGesturesLib(self.autodir)
        gesture_lib.remove_existing_test_files()
        gesture_lib.download_files(gesture_lib.get_default_test_file_list(
            gesture_lib.determine_model()))

EXAMPLE: the following is an example of code that might be added to the
         hardware_Trackpad/trackpad_record test to upload gesture files
         after recording:
...
import cros_gestures_lib
...
    def record_all(self):
        ...
        gesture_lib = cros_gestures_lib.CrosGesturesLib(self.autodir)
        gesture_lib.upload_files()
"""

__author__ = 'truty@chromium.org (Mike Truty)'

import json
import os
import shutil

import common_util
import trackpad_util


GESTURE_BASE_URI = 'http://chromeos-gestures.appspot.com'


class CrosGesturesLib(object):
    """This class organizes code to download/upload gesture test files."""
    temp_dir = '/tmp'

    def __init__(self, autodir):
        """Determine the gesture test files location."""
        local_path = os.path.join(autodir, 'tests/hardware_Trackpad')
        gesture_files_path_conf = trackpad_util.read_trackpad_test_conf(
            'gesture_files_path', local_path)
        self.gesture_files_path = os.path.join(local_path,
                                               gesture_files_path_conf)
        if not os.path.isdir(self.gesture_files_path):
            os.makedirs(self.gesture_files_path)
        self.gesture_files_old = os.path.join(self.temp_dir,
                                              'cros_gestures_old')
        if not os.path.isdir(self.gesture_files_old):
            os.makedirs(self.gesture_files_old)

    def remove_existing_test_files(self):
        """Cleanup existing files for a fresh test."""
        existing = os.listdir(self.gesture_files_path)
        for f in existing:
              # Save existing files under /tmp as a safety net.
              full_temp_name = os.path.join(self.gesture_files_old, f)
              if os.path.isfile(full_temp_name):
                  os.remove(full_temp_name)
              shutil.move(os.path.join(self.gesture_files_path, f),
                          full_temp_name)

    def determine_model(self):
        """Inspect the machine to determine the model."""
        cmd = 'cat /etc/lsb-release | grep CHROMEOS_RELEASE_BOARD'
        line = common_util.simple_system_output(cmd)
        if not line or line.find('=') < 0:
            return None
        return line.split('=')[1].strip().split('-')[-1]

    def get_default_test_file_list(self, model):
        """Using the model of the test machine, retrieve list of test files."""
        wget_cmd = 'wget --timeout=30 --tries=5 --no-proxy -qO- "%s"'
        file_list_uri = '%s/modeldefaultfiles?json=true&model=%s'
        cmd = wget_cmd % (file_list_uri % (GESTURE_BASE_URI,
                                           self.determine_model()))
        return json.loads(common_util.simple_system_output(cmd))


    def download_files(self, file_list, ignore_failures=False):
        """Given file list, download them to a conf file specified location."""
        rc  = 0
        wget_cmd = 'wget --timeout=30 --tries=5 --no-proxy -qO "%s" "%s"'
        for f in file_list:
            cmd = wget_cmd % (os.path.join(self.gesture_files_path,
                                           os.path.basename(f)), f)
            rc = common_util.simple_system(cmd)
        # TODO(Truty): Verify the files using md5.
        return rc

    def upload_files(self):
        """Use the config file to find file location and upload all files.
        If an uploaded version of the file already exists the upload silently
        fails to allow for repeat attempts to upload without clearing files.
        """
        rc = 0
        cg_cmd = '/usr/local/cros_gestures/cros_gestures'
        upload_cmd = '%s upload "%s"'
        for f in os.listdir(self.gesture_files_path):
            full_gesture_path = os.path.join(self.gesture_files_path, f)
            rc = common_util.simple_system(upload_cmd % (cg_cmd,
                                                         full_gesture_path))
            if rc:
                break
        return rc
