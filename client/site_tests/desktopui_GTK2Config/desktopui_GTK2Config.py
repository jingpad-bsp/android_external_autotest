# Copyright (c) 2011 The Chromium OS Authors. All rights reserved.
# Use of this source code is governed by a BSD-style license that can be
# found in the LICENSE file.

import os
import utils
from autotest_lib.client.bin import test
from autotest_lib.client.common_lib import autotemp

class desktopui_GTK2Config(test.test):
    version = 1

    _GTK2_CONFDIR = "/etc/gtk-2.0"
    _CONFIG_CHECKS = {
        "gtk.immodules": "/usr/bin/gtk-query-immodules-2.0",
        "gdk-pixbuf.loaders": "/usr/bin/gdk-pixbuf-query-loaders",
    }

    def run_once(self):
      for conf,cmd in self._CONFIG_CHECKS.items():
        temp = autotemp.tempfile(unique_id=conf)
        utils.system("%s > %s" % (cmd, temp.name))
        utils.system("diff -qr %s %s" % (os.path.join(self._GTK2_CONFDIR, conf),
                                         temp.name))
        temp.clean()
