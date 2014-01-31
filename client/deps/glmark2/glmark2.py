#!/usr/bin/python

# Copyright (c) 2014 The Chromium OS Authors. All rights reserved.
# Use of this source code is governed by a BSD-style license that can be
# found in the LICENSE file.

import common, os
from autotest_lib.client.bin import utils

version = 2

def setup(top_dir):
    dst_bin = top_dir + '/glmark2'
    dst_data = top_dir + '/data'

    # Avoid writing on subsequent setup() calls
    if (os.path.exists(dst_bin)):
        return

    # Look for glmark2 or glmark2-es2, installed by app-benchmarks/glmark2
    # Prefer glmark2 if both are present.
    src_bin = os.environ['SYSROOT'] + '/usr/bin/glmark2'
    if not os.path.exists(src_bin):
        src_bin = os.environ['SYSROOT'] + '/usr/bin/glmark2-es2'
    if not os.path.exists(src_bin):
        # TODO: throw an exception here?
        return

    src_data = os.environ['SYSROOT'] + '/usr/share/glmark2'

    utils.run('cp %s %s' % (src_bin, dst_bin))
    # Copy glmark2 models, shaders and textures
    utils.run('cp -R %s %s' % (src_data, dst_data))

pwd = os.getcwd()
utils.update_version(pwd + '/src', False, version, setup, pwd)
