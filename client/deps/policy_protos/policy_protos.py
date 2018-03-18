#!/usr/bin/python

# Copyright 2018 The Chromium Authors. All rights reserved.
# Use of this source code is governed by a BSD-style license that can be
# found in the LICENSE file.
"""Compile policy protobuf Python files.

The policy protos are used by a bunch of policy_* and login_* autotests.
"""

import os
import pipes
from autotest_lib.client.bin import utils

version = 1

# cloud_policy.proto and chrome_extension_policy.proto are unreferenced here,
# but used by policy_testserver.py in the Chromium code base, so don't remote
# them!
PROTO_DEFS = [
        'chrome_device_policy.proto', 'device_management_backend.proto',
        'cloud_policy.proto', 'chrome_extension_policy.proto'
]


def setup(top_dir):
    sysroot = os.environ['SYSROOT']
    proto_path = os.path.join(sysroot, 'usr/share/protofiles/')
    cmd = (['protoc', '--proto_path=' + proto_path, '--python_out=' + top_dir]
           + [os.path.join(proto_path, proto_def) for proto_def in PROTO_DEFS])
    utils.run(' '.join(pipes.quote(arg) for arg in cmd))
    return


pwd = os.getcwd()
utils.update_version(os.path.join(pwd, 'src'), False, version, setup, pwd)
