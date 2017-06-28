# Copyright 2017 The Chromium OS Authors. All rights reserved.
# Use of this source code is governed by a BSD-style license that can be
# found in the LICENSE file.

"""Shared constants and methods for result utilities."""

# Following are key names for directory summaries. The keys are started with /
# so it can be differentiated with a valid file name. The short keys are
# designed for smaller file size of the directory summary.

# Original size of the directory or file
ORIGINAL_SIZE_BYTES = '/S'
# Size of the directory or file after trimming
TRIMMED_SIZE_BYTES = '/T'
# Size of the directory or file being collected from client side
COLLECTED_SIZE_BYTES = '/C'
# A dictionary of sub-directories' summary: name: {directory_summary}
DIRS = '/D'
# Default root directory name. To allow summaries to be merged effectively, all
# summaries are collected with root directory of ''
ROOT_DIR = ''