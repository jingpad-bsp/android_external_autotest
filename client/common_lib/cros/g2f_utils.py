# Copyright 2018 The Chromium OS Authors. All rights reserved.
# Use of this source code is governed by a BSD-style license that can be
# found in the LICENSE file.

import logging, os
import time

from autotest_lib.client.common_lib import error, utils, logging_manager

def StartU2fd(client):
    """Starts u2fd on the client.

    @param client: client object to run commands on.
    """
    client.run('stop u2fd', ignore_status=True)
    old_dev = client.run('ls /dev/hidraw*').stdout.strip().split('\n')
    client.run_background('u2fd --force_g2f')

    # TODO(louiscollard): Replace this with something less fragile.
    cr50_dev = set()
    timeout_count = 0
    while (len(cr50_dev) == 0 and timeout_count < 5):
      time.sleep(1)
      timeout_count += 1
      new_dev = client.run('ls /dev/hidraw*').stdout.strip().split('\n')
      cr50_dev = set(new_dev) - set(old_dev)

    return cr50_dev.pop()

def G2fRegister(client, dev, challenge, application):
    """Returns a dictionary with TPM status.

    @param client: client object to run commands on.
    """
    return client.run('g2ftool --reg --dev=' + dev +
                      ' --challenge=' + challenge +
                      ' --application=' + application,
                      ignore_status=True)

def G2fAuth(client, dev, challenge, application, key_handle):
    """Returns a dictionary with TPM status.

    @param client: client object to run commands on.
    """
    return client.run('g2ftool --auth --dev=' + dev +
                      ' --challenge=' + challenge +
                      ' --application=' + application +
                      ' --key_handle=' + key_handle,
                      ignore_status=True)
