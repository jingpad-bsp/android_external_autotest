# Copyright (c) 2012 The Chromium OS Authors. All rights reserved.
# Use of this source code is governed by a BSD-style license that can be
# found in the LICENSE file.

import logging
import xmlrpclib

import common

from autotest_lib.client.common_lib import global_config


RPM_FRONTEND_URI = global_config.global_config.get_config_value('CROS',
        'rpm_frontend_uri', type=str, default='')


class RemotePowerException(Exception):
    """This is raised when we fail to set the state of the device's outlet."""
    pass


def set_power(hostname, new_state):
    client = xmlrpclib.ServerProxy(RPM_FRONTEND_URI, verbose=False)
    if not client.queue_request(hostname, new_state):
        error_msg = ('Failed to change outlet status for host: %s to '
                     'state: %s.' % (hostname, new_state))
        logging.error(error_msg)
        raise RemotePowerException(error_msg)
