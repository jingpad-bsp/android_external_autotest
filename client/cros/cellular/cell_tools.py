# Copyright (c) 2011 The Chromium OS Authors. All rights reserved.
# Use of this source code is governed by a BSD-style license that can be
# found in the LICENSE file.

"""Utilities for cellular tests."""
import logging

from autotest_lib.client.cros import flimflam_test_path
import flimflam


class Error(Exception):
    pass


CONFIG_TIMEOUT=30


def ConnectToCellNetwork(flim, config_timeout=CONFIG_TIMEOUT):
    """Attempts to connect to a cell network using FlimFlam.

    Args:
    flim:  A flimflam object
    config_timeout:    Timeout (in seconds) before giving up on connect

    Raises:
    Error if connection fails or times out
    """
    service = flim.FindCellularService()
    if not service:
        raise Error('Could not find cell service')

    logging.info('Connecting to cell service: %s', service)
    success, status = flim.ConnectService(
        service=service,
        config_timeout=config_timeout)

    if not success:
      # TODO(rochberg):  Turn off autoconnect
      if 'Error.AlreadyConnected' not in status['reason']:
        raise Error('Could not connect: %s.' % status)

    connected_states = ['portal', 'online']
    state = flim.WaitForServiceState(service=service,
                                     expected_states=connected_states,
                                     timeout=15,
                                     ignore_failure=True)[0]
    if not state in connected_states:
      raise Error('Still in state %s' % state)

    return state


class OtherDeviceShutdownManager(object):
  """Context manager that shuts down other devices.
  Usage:
      with cell_tools.OtherDeviceShutdownManager(flim, 'cellular'):
        block

  TODO(rochberg):  Replace flimflam.DeviceManager with this
  """

  def __init__(self, device_type, flim):
    self.device_manager = flimflam.DeviceManager(flim)
    self.device_manager.ShutdownAllExcept(device_type)

  def __enter__(self):
    return self

  def __exit__(self, exception, value, traceback):
    self.device_manager.RestoreDevices()
    return False
