# Copyright (c) 2013 The Chromium OS Authors. All rights reserved.
# Use of this source code is governed by a BSD-style license that can be
# found in the LICENSE file.

"""FAFT configuration overrides for Stout."""


class Values():
    broken_warm_reset = True
    broken_rec_mode = True
    key_matrix_layout = 2
    key_checker = [[0x29, 'press'],
                   [0x32, 'press'],
                   [0x32, 'release'],
                   [0x29, 'release'],
                   [0x43, 'press'],
                   [0x43, 'release']]
