# Copyright (c) 2013 The Chromium OS Authors. All rights reserved.
# Use of this source code is governed by a BSD-style license that can be
# found in the LICENSE file.

import os
import sys
dirname = os.path.dirname(sys.modules[__name__].__file__)
relative_autotest_dir = os.path.join(dirname, os.pardir, os.pardir, os.pardir)
autotest_dir = os.path.abspath(relative_autotest_dir)
client_dir = os.path.join(autotest_dir, "client")
sys.path.insert(0, client_dir)
import setup_modules
sys.path.pop(0)
setup_modules.setup(base_path=autotest_dir, root_module_name="autotest_lib")
