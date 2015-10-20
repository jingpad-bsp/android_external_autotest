# Copyright 2015 The Chromium OS Authors. All rights reserved.
# Use of this source code is governed by a BSD-style license that can be
# found in the LICENSE file.

SUPPORTED_BOARDS = ['butterfly', 'daisy', 'falco', 'link', 'nyan_big',
                    'parrot', 'peppy', 'peach_pi', 'peach_pit', 'samus',
                    'squawks', 'veyron_jerry']

DESIRED_WIDTH = 864
DESIRED_HEIGHT = 494

TEST_DIR = '/tmp/test'
GOLDEN_CHECKSUMS_FILENAME = 'golden_checksums.txt'
GOLDEN_CHECKSUM_REMOTE_BASE_DIR = (
    'https://storage.googleapis.com/chromiumos-test-assets-public'
    '/golden_images_video_image_comparison')

IMAGE_FORMAT = 'png'
FCOUNT = 30
MAX_FRAME_REPEAT_COUNT = 5
MAX_DIFF_TOTAL_FCOUNT = 10
MAX_NONMATCHING_FCOUNT = 5