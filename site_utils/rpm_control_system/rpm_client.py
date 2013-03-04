# Copyright (c) 2012 The Chromium OS Authors. All rights reserved.
# Use of this source code is governed by a BSD-style license that can be
# found in the LICENSE file.

import logging
import xmlrpclib

import common

from config import rpm_config
from autotest_lib.client.common_lib import global_config
from autotest_lib.client.common_lib.cros import retry


RPM_FRONTEND_URI = global_config.global_config.get_config_value('CROS',
        'rpm_frontend_uri', type=str, default='')
RPM_CALL_TIMEOUT_MINS = rpm_config.getint('RPM_INFRASTRUCTURE',
                                          'call_timeout_mins')


class RemotePowerException(Exception):
    """This is raised when we fail to set the state of the device's outlet."""
    pass


def set_power(hostname, new_state):
    """Sends the power state change request to the RPM Infrastructure.

    @param hostname: host who's power outlet we want to change.
    @param new_state: State we want to set the power outlet to.
    """
    client = xmlrpclib.ServerProxy(RPM_FRONTEND_URI, verbose=False)
    timeout, result = retry.timeout(client.queue_request,
                                    args=(hostname, new_state),
                                    timeout_sec=RPM_CALL_TIMEOUT_MINS * 60,
                                    default_result=False)
    if timeout:
        raise RemotePowerException('Call to RPM Infrastructure timed out.')
    if not result:
        error_msg = ('Failed to change outlet status for host: %s to '
                     'state: %s.' % (hostname, new_state))
        logging.error(error_msg)
        raise RemotePowerException(error_msg)