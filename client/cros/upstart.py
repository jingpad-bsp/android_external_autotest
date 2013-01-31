# Copyright (c) 2011 The Chromium OS Authors. All rights reserved.
# Use of this source code is governed by a BSD-style license that can be
# found in the LICENSE file.

# NB: this code is downloaded for use by site_system_suspend.py;
# beware of adding dependencies on client libraries such as utils

"""Provides utility methods/classes for interacting with upstart"""

import os

def ensure_running(service_name):
    cmd = 'initctl status %s | grep start/running' % service_name
    os.system(cmd)

class ServiceStopper(object):
    """Class to manage CrOS services.
    Public attributes:
      services_to_stop: list of services that should be stopped

   Public constants:
      POWER_DRAW_SERVICES: list of services that influence power test in
    unpredictable/undesirable manners.

    Public methods:
      stop_sevices: stop running system services.
      restore_services: restore services that were previously stopped.

    Private attributes:
      _services_stopped: list of services that were successfully stopped
    """

    POWER_DRAW_SERVICES = ['powerd', 'update-engine', 'bluetoothd']

    def __init__(self, services_to_stop=[]):
        """Initialize instance of class.

        By Default sets an empty list of services.
        """
        self.services_to_stop = services_to_stop
        self._services_stopped = []


    def stop_services(self):
        """Turn off managed services."""

        for service in self.services_to_stop:
            cmd = 'status %s' % service
            is_stopped = utils.system_output(cmd).find('stop/waiting') != -1
            if is_stopped:
                continue
            try:
                utils.system('stop %s' % service)
                self._services_stopped.append(service)
            except error.CmdError as e:
                logging.warning('Error stopping service %s. %s',
                                service, str(e))


    def restore_services(self):
        """Restore services that were stopped."""
        for service in reversed(self._services_stopped):
            utils.system('start %s' % service, ignore_status=True)
        self._services_stopped = []
