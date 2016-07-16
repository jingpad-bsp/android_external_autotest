# Copyright 2016 The Chromium OS Authors. All rights reserved.
# Use of this source code is governed by a BSD-style license that can be
# found in the LICENSE file.

AUTHOR = "Chrome OS Project, chromeos-video@google.com"
NAME = "video_ChromeHWDecodeUsed.vp8.arc"
PURPOSE = "Verify that VP8 video decode acceleration works in Chrome"
CRITERIA = """
This test will fail if VDA doesn't work with Chrome navigating to a webm file.
"""
TIME = "SHORT"
ATTRIBUTES = "suite:arc-bvt-cq, suite:bvt-cq"
TEST_CATEGORY = "General"
TEST_CLASS = "video"
TEST_TYPE = "client"
DEPENDENCIES = "hw_video_acc_vp8, arc"
JOB_RETRIES = 2
BUG_TEMPLATE = {
    'labels': ['OS-Chrome', 'VideoTestFailure'],
    'cc': ['chromeos-video-test-failures@google.com'],
}
ARC_MODE = "enabled"

DOC = """
This test verifies VP8 video decode acceleration works.
"""

job.run_test('video_ChromeHWDecodeUsed', is_mse=0, video_file='720_vp8.webm',
             arc_mode=ARC_MODE)
