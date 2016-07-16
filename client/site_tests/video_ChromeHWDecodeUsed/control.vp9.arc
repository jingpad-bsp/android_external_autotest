# Copyright 2016 The Chromium OS Authors. All rights reserved.
# Use of this source code is governed by a BSD-style license that can be
# found in the LICENSE file.

AUTHOR = "Chrome OS Project, chromeos-video@google.com"
NAME = "video_ChromeHWDecodeUsed.vp9.arc"
PURPOSE = "Verify that VP9 video decode acceleration works in Chrome"
CRITERIA = """
This test will fail if VDA doesn't work with Chrome navigating to a VP9 webm
file.
"""
TIME = "SHORT"
ATTRIBUTES = "suite:arc-bvt-cq, suite:bvt-cq"
TEST_CATEGORY = "General"
TEST_CLASS = "video"
TEST_TYPE = "client"
DEPENDENCIES = "hw_video_acc_vp9, arc"
JOB_RETRIES = 2
BUG_TEMPLATE = {
    'labels': ['OS-Chrome', 'VideoTestFailure'],
}
ARC_MODE = "enabled"

DOC = """
This test verifies VP9 video decode acceleration works.
"""

job.run_test('video_ChromeHWDecodeUsed', is_mse=0, video_file='720.webm',
             arc_mode=ARC_MODE)
