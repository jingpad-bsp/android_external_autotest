# Copyright (c) 2011 The Chromium OS Authors. All rights reserved.
# Use of this source code is governed by a BSD-style license that can be
# found in the LICENSE file.

import os


# Override default parser with our site parser.
def parser_path(install_dir):
    return os.path.join(install_dir, 'tko', 'site_parse')
