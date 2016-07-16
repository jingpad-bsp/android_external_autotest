# Copyright 2016 The Chromium OS Authors. All rights reserved.
# Use of this source code is governed by a BSD-style license that can be
# found in the LICENSE file.

AUTHOR = "Chrome OS Project, chromeos-video@google.com"
NAME = "video_ChromeHWDecodeUsed.h264.arc"
PURPOSE = "Verify that H.264 video decode acceleration works in Chrome"
CRITERIA = """
This test will fail if VDA doesn't work with Chrome navigating to an mp4 file.
"""
TIME = "SHORT"
ATTRIBUTES = "suite:arc-bvt-cq, suite:bvt-cq"
TEST_CATEGORY = "General"
TEST_CLASS = "video"
TEST_TYPE = "client"
DEPENDENCIES = "hw_video_acc_h264, arc"
JOB_RETRIES = 2
BUG_TEMPLATE = {
    'labels': ['OS-Chrome', 'VideoTestFailure'],
    'cc': ['chromeos-video-test-failures@google.com'],
}
ARC_MODE = "enabled"

DOC = """
This test verifies H.264 video decode acceleration works.
"""

job.run_test('video_ChromeHWDecodeUsed', is_mse=0, video_file='720.mp4',
             arc_mode=ARC_MODE)
