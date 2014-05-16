# Copyright (c) 2012 The Chromium OS Authors. All rights reserved.
# Use of this source code is governed by a BSD-style license that can be
# found in the LICENSE file.

import os, shutil

# Setup autotest_lib path by importing common.
import common
from autotest_lib.client.bin import utils


version = 1


def setup(setup_dir):
    """Stores a copy of the chromite cbuildbot source code for use on a DUT."""
    my_dep_dir = os.path.join(os.environ['CHROMEOS_ROOT'], 'chromite',
                              'cbuildbot')
    shutil.copytree(my_dep_dir, setup_dir)


work_dir = os.path.join(os.getcwd(), 'src')
utils.update_version(os.getcwd(), True, version, setup, work_dir)
