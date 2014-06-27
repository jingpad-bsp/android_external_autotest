#!/usr/bin/env python
# Copyright (c) 2012 The Chromium OS Authors. All rights reserved.
# Use of this source code is governed by a BSD-style license that can be
# found in the LICENSE file.

import dbus
import dbus.mainloop.glib
import gobject
import logging
import time

from autotest_lib.client.bin import test, utils
from autotest_lib.client.common_lib import error
from autotest_lib.client.cros import backchannel, network
from autotest_lib.client.cros.cellular import mm
from autotest_lib.client.cros.cellular.pseudomodem import pseudomodem_context
from autotest_lib.client.cros.mainloop import GenericTesterMainLoop
from autotest_lib.client.cros.mainloop import ExceptionForward

from autotest_lib.client.cros import flimflam_test_path
import flimflam

DEFAULT_TEST_TIMEOUT_S=600
DEVICE_TIMEOUT=60

class DisableTester(GenericTesterMainLoop):
  def __init__(self, *args, **kwargs):
    super(DisableTester, self).__init__(*args, **kwargs)

  @ExceptionForward
  def perform_one_test(self):
    self.configure()
    disable_delay_ms = (
        self.test_kwargs.get('delay_before_disable_ms', 0) +
        self.test.iteration *
        self.test_kwargs.get('disable_delay_per_iteration_ms', 0))
    gobject.timeout_add(disable_delay_ms, self.start_disable)
    self.start_test()

  @ExceptionForward
  def connect_success_handler(self, *ignored_args):
    logging.info('connect succeeded')
    self.requirement_completed('connect')

  @ExceptionForward
  def connect_error_handler(self, e):
    # We disabled while connecting; error is OK
    logging.info('connect errored: %s' % e)
    self.requirement_completed('connect')

  @ExceptionForward
  def start_disable(self):
    logging.info('disabling')
    self.disable_start = time.time()
    self.enable(False)

  @ExceptionForward
  def disable_success_handler(self):
    disable_elapsed = time.time() - self.disable_start
    self.assert_(disable_elapsed <
                 1.0 + self.test_kwargs.get('async_connect_sleep_ms', 0))
    self.requirement_completed('disable')

  @ExceptionForward
  def get_status_success_handler(self, status):
    logging.info('Got status')
    self.requirement_completed('get_status', warn_if_already_completed=False)
    if self.status_delay_ms:
      gobject.timeout_add(self.status_delay_ms, self.start_get_status)

  def after_main_loop(self):
    enabled = self.enabled()
    logging.info('Modem enabled: %s', enabled)
    self.assert_(enabled == 0)
    # Will return happily if no Gobi present
    network.ClearGobiModemFaultInjection()


class FlimflamDisableTester(DisableTester):
  """Tests that disable-while-connecting works at the flimflam level.
  Expected control flow:

  * self.configure() called; registers self.disable_property_changed
    to be called when device is en/disabled

  * Parent class sets a timer that calls self.enable(False) when it expires.

  * start_test calls start_connect() which sends a connect request to
    the device.

  * we wait for the modem to power off, at which point
    disable_property_changed (registered above) will get called

  * disable_property_changed() completes the 'disable' requirement,
    and we're done.
"""
  def __init__(self, *args, **kwargs):
    super(FlimflamDisableTester, self).__init__(*args, **kwargs)

  def disable_property_changed(self, property, value, *args, **kwargs):
    self.assert_(not value)
    self.disable_success_handler()

  def start_test(self):
    # We would love to add requirements based on connect, but in many
    # scenarios, there is no observable response to a cancelled
    # connect: We issue a connect, it returns instantly to let us know
    # that the connect has started, but then the disable takes effect
    # and the connect fails.  We don't get a state change because no
    # state change has happened: the modem never got to a different
    # state before we cancelled
    self.remaining_requirements = set(['disable'])
    self.start_connect()

  def compare_powered_state(self, device, enable):
    return device.GetProperties()['Powered'] == enable

  def synchronous_enable(self, device, value, timeout_s=DEVICE_TIMEOUT):
    try:
      if value:
        device.Enable(timeout=timeout_s)
      else:
        device.Disable(timeout=timeout_s)
    except dbus.exceptions.DBusException, e:
      if e._dbus_error_name != 'org.chromium.flimflam.Error.InProgress':
        raise
    utils.poll_for_condition(
        lambda: self.compare_powered_state(device, value),
        error.TestError('Timed out waiting to set power to %s' % value),
        timeout=timeout_s)

  def configure(self):
    self.flimflam = flimflam.FlimFlam()
    self.flimflam.SetDebugTags(
        'dbus+service+device+modem+cellular+portal+network+manager')

    # ModemManager may be in an illegal state if this test is run multiple
    # times in succession. Sleep here to make sure that ResetAllModems suceeds.
    time.sleep(5)
    network.ResetAllModems(self.flimflam)

    self.cellular_device = self.flimflam.FindCellularDevice()
    if self.cellular_device is None:
      raise error.TestError("Could not find cellular device")

    self.synchronous_enable(self.cellular_device, False)
    self.synchronous_enable(self.cellular_device, True)

    self.cellular_service = self.flimflam.FindCellularService()
    if self.cellular_service is None:
      raise error.TestError("Could not find cellular service")

    self.assert_(self.cellular_device.GetProperties()['Address'].lower() in
                 self.cellular_service.GetProperties()['Device'])

    self.flimflam.bus.add_signal_receiver(self.dispatch_property_changed,
                                          signal_name='PropertyChanged')

  @ExceptionForward
  def expect_einprogress_handler(self, e):
    self.assert_(e._dbus_error_name == 'org.chromium.flimflam.Error.InProgress')

  def enable(self, value):
    self.assert_(not value)  # If we're ever called with true, need to
                             # plumb expected value to
                             # self.disable_property_changed
    self.property_changed_actions['Powered'] = self.disable_property_changed

    if value:
      self.cellular_device.Enable(
          reply_handler=self.ignore_handler,
          error_handler=self.expect_einprogress_handler)
    else:
      self.cellular_device.Disable(
          reply_handler=self.ignore_handler,
          error_handler=self.expect_einprogress_handler)

  @ExceptionForward
  def start_connect(self):
    logging.info('connecting')

    def log_connect_event(property, value, *ignored_args):
      logging.info('%s property changed: %s' % (property, value))

    self.property_changed_actions['Connected'] = log_connect_event

    # Contrary to documentation, Connect just returns when it has
    # fired off the lower-level dbus messages.  So a success means
    # nothing to us.  But a failure means it didn't even try.
    self.cellular_service.Connect(
        reply_handler=self.ignore_handler,
        error_handler=self.build_error_handler('Connect'))

  def enabled(self):
    return self.cellular_device.GetProperties()['Powered']


class ModemDisableTester(DisableTester):
  """Tests that disable-while-connecting works at the modem-manager level.

  Expected control flow:

  * configure() is called.

  * Parent class sets a timer that calls self.enable(False) when it
    expires.

  * start_test calls start_connect() which sends a connect request to
    the device, also sets a timer that calls GetStatus on the modem.

  * wait for all three (connect, disable, get_status) to complete.
"""
  def __init__(self, *args, **kwargs):
    super(ModemDisableTester, self).__init__(*args, **kwargs)

  def is_gobi(self):
    return 'Gobi' in self.modem_path

  def start_test(self):
    self.remaining_requirements = set(['connect', 'disable'])

    # Only cromo/gobi-cromo-plugin maintain the invariant that GetStatus
    # will always succeed, so we only check it if the modem is a Gobi.
    if self.is_gobi():
      self.remaining_requirements.add('get_status')
      self.status_delay_ms = self.test_kwargs.get('status_delay_ms', 200)
      gobject.timeout_add(self.status_delay_ms, self.start_get_status)

    self.start_connect()

  def configure(self):
    self.modem_manager, self.modem_path = mm.PickOneModem('')
    self.modem = self.modem_manager.GetModem(self.modem_path)
    self.simple_modem = self.modem.SimpleModem()

    logging.info('Modem path: %s' % self.modem_path)

    if self.is_gobi():
      self.configure_gobi()
    else:
      self.configure_non_gobi()

    self.modem.Enable(False)
    self.modem.Enable(True)

  def configure_gobi(self):
    gobi_modem = self.modem.GobiModem()

    if 'async_connect_sleep_ms' in self.test_kwargs:
      sleep_ms = self.test_kwargs.get('async_connect_sleep_ms', 0)
      logging.info('Sleeping %d ms before connect' % sleep_ms)
      gobi_modem.InjectFault('AsyncConnectSleepMs', sleep_ms)

    if 'connect_fails_with_error_sending_qmi_request' in self.test_kwargs:
      logging.info('Injecting QMI failure')
      gobi_modem.InjectFault('ConnectFailsWithErrorSendingQmiRequest', 1)

  def configure_non_gobi(self):
    # Check to make sure no Gobi-specific arguments were specified.
    if 'async_connect_sleep_ms' in self.test_kwargs:
      raise error.TestError(
        'async_connect_sleep_ms on non-Gobi modem')
    if 'connect_fails_with_error_sending_qmi_request' in self.test_kwargs:
      raise error.TestError(
        'connect_fails_with_error_sending_qmi_request on non-Gobi modem')

  @ExceptionForward
  def start_connect(self):
    logging.info('connecting')

    retval = self.simple_modem.Connect(
        {},
        reply_handler=self.connect_success_handler,
        error_handler=self.connect_error_handler)
    logging.info('connect call made.  retval = %s', retval)


  @ExceptionForward
  def start_get_status(self):
    # Keep on calling get_status to make sure it works at all times
    self.simple_modem.GetStatus(
        reply_handler=self.get_status_success_handler,
        error_handler=self.build_error_handler('GetStatus'))

  def enabled(self):
    return self.modem.GetModemProperties().get('Enabled', -1)

  def enable(self, value):
    self.modem.Enable(value,
                      reply_handler=self.disable_success_handler,
                      error_handler=self.build_error_handler('Enable'))


class network_3GDisableWhileConnecting(test.test):
  version = 1
  def run_once(
      self, use_pseudomodem=False, pseudomodem_family='3GPP', **kwargs):
    timeout_s = kwargs.get('timeout_s', DEFAULT_TEST_TIMEOUT_S)

    with backchannel.Backchannel():
      dbus.mainloop.glib.DBusGMainLoop(set_as_default=True)
      self.main_loop = gobject.MainLoop()
      self.bus = dbus.SystemBus()
      with pseudomodem_context.PseudoModemManagerContext(
              use_pseudomodem,
              {'family' : pseudomodem_family},
              bus=self.bus):
        try:
          logging.info('Flimflam-level test')
          flimflam = FlimflamDisableTester(self,
                                           self.main_loop,
                                           timeout_s=timeout_s)
          flimflam.run(**kwargs)

          logging.info('Modem-level test')
          modem = ModemDisableTester(self,
                                     self.main_loop,
                                     timeout_s=timeout_s)
          modem.run(**kwargs)
        finally:
          network.ClearGobiModemFaultInjection()
