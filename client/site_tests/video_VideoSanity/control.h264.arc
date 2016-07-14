# Copyright 2016 The Chromium OS Authors. All rights reserved.
# Use of this source code is governed by a BSD-style license that can be
# found in the LICENSE file.

AUTHOR = 'Chrome OS Project, chromeos-video@google.com'
NAME = 'video_VideoSanity.h264.arc'
PURPOSE = 'Verify that Chrome media and video works'
CRITERIA = """
This test will fail if Chrome media is not enable or video doesn't play.
"""
ATTRIBUTES = "suite:arc-bvt-cq, suite:bvt-cq"
TIME = 'SHORT'
TEST_CATEGORY = 'General'
TEST_CLASS = 'video'
TEST_TYPE = 'client'
DEPENDENCIES = "arc"
JOB_RETRIES = 2
BUG_TEMPLATE = {
    'labels': ['OS-Chrome', 'VideoTestFailure'],
    'cc': ['chromeos-video-test-failures@google.com'],
}
ARC_MODE = 'enabled'

DOC = """
This test verify the media elements and video sanity.
"""

job.run_test('video_VideoSanity', video_file='720.mp4', arc_mode=ARC_MODE)
