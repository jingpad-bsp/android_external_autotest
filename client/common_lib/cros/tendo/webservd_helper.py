# Copyright 2015 The Chromium OS Authors. All rights reserved.
# Use of this source code is governed by a BSD-style license that can be
# found in the LICENSE file.

from autotest_lib.client.common_lib import utils

def webservd_is_installed(host=None):
    """Check if the webservd binary is installed.

    @param host: Host object if we're interested in a remote host.
    @return True iff webservd is installed in this system.

    """
    run = utils.run
    if host is not None:
        run = host.run
    result = run('if [ -f /usr/bin/webservd ]; then exit 0; fi; exit 1',
                 ignore_status=True)
    if result.exit_status == 0:
        return True
    return False
