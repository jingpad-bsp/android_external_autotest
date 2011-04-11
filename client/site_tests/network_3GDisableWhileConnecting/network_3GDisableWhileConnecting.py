#!/usr/bin/env python
# Copyright (c) 2011 The Chromium OS Authors. All rights reserved.
# Use of this source code is governed by a BSD-style license that can be
# found in the LICENSE file.

from autotest_lib.client.bin import test, utils
from autotest_lib.client.common_lib import error

import logging, pprint, time, traceback, sys
import dbus, dbus.mainloop.glib, glib, gobject

from autotest_lib.client.cros import flimflam_test_path
import mm, flimflam

import os

def ExceptionForward(func):
  def wrapper(self, *args, **kwargs):
    try:
      return func(self, *args, **kwargs)
    except Exception, e:
      logging.warning('Saving exception: %s' % e)
      logging.warning(''.join(traceback.format_exception(*sys.exc_info())))
      self._forwarded_exception = e
      self.main_loop.quit()
      return False
  return wrapper

class DisconnnectTesterMainLoop(object):
  version = 1

  def __init__(self, test, main_loop):
    self._forwarded_exception = None
    self.main_loop = main_loop
    self.test = test

  def assert_(self, arg):
    self.test.assert_(self, arg)

  @ExceptionForward
  def timeout_main_loop(self):
    logging.warning('Requirements unsatisfied upon timeout: %s' %
                    self.remaining_requirements)
    self.main_loop.quit()
    raise error.TestFail('Main loop timed out')

  def requirement_completed(self, requirement, warn_if_already_completed=True):
    """Record that a requirement was completed.  Exit if all are."""
    should_log = True
    try:
      self.remaining_requirements.remove(requirement)
    except KeyError:
      if warn_if_already_completed:
        logging.warning('requirement %s was not present to be completed',
                        requirement)
      else:
        should_log = False

    if not self.remaining_requirements:
      logging.info('All requirements satisfied')
      self.main_loop.quit()
    else:
      if should_log:
        logging.info('Requirement %s satisfied.  Remaining: %s' %
                     (requirement, self.remaining_requirements))

  def perform_one_test(self):
    """Subclasses override this function to do their testing."""
    raise Exception('perform_one_test must be overridden')

  @ExceptionForward
  def generic_dbus_error_handler(self, e):
    raise error.TestFail('Dbus call failed: %s' % e)

  def run(self, **kwargs):
    self.test_args = kwargs
    gobject.timeout_add(int(self.test_args.get('timeout_s', 10) * 1000),
                        self.timeout_main_loop)
    gobject.idle_add(self.perform_one_test)
    self.main_loop.run()
    if self._forwarded_exception:
      raise self._forwarded_exception
    self.after_main_loop()

class ModemDisableTester(DisconnnectTesterMainLoop):
  def __init__(self, test, main_loop):
    super(ModemDisableTester, self).__init__(test, main_loop)
    self.remaining_requirements = set(['connect', 'disable', 'get_status'])

  def modem_enabled(self):
    return self.modem_manager.Properties(self.modem_path).get('Enabled', -1)

  def configure_modem(self):
    self.modem_manager, self.modem_path = mm.PickOneModem('')
    self.modem = self.modem_manager.Modem(self.modem_path)
    self.simple_modem = self.modem_manager.SimpleModem(self.modem_path)
    self.gobi_modem = self.modem_manager.GobiModem(self.modem_path)

    if self.gobi_modem:
      sleep_ms = self.test_args.get('async_connect_sleep_ms', 0)

      # Tell the modem manager to sleep this long before completing a
      # connect
      self.gobi_modem.InjectFault('AsyncConnectSleepMs', sleep_ms)

    self.modem.Enable(False)
    self.modem.Enable(True)

  @ExceptionForward
  def perform_one_test(self):
    self.configure_modem()
    logging.info('connecting')

    retval = self.simple_modem.Connect(
        {},
        reply_handler=self.connect_success_handler,
        error_handler=self.connect_error_handler)
    logging.info('connect call made.  retval = %s', retval)

    disable_delay_ms = (
        self.test_args.get('delay_before_disable_ms', 0) +
        self.test.iteration *
        self.test_args.get('disable_delay_per_iteration_ms', 0))
    gobject.timeout_add(disable_delay_ms, self.start_disable)

    self.status_delay_ms = self.test_args.get('status_delay_ms', 200)
    gobject.timeout_add(self.status_delay_ms, self.start_get_status)

  @ExceptionForward
  def connect_success_handler(self, *ignored_args):
    logging.info('Reply done')
    self.requirement_completed('connect')

  @ExceptionForward
  def connect_error_handler(self, *ignored_args):
    logging.info('Reply errored.')
    self.requirement_completed('connect')

  @ExceptionForward
  def start_disable(self):
    logging.info('disabling')
    self.disable_start = time.time()
    self.modem.Enable(False,
                      reply_handler=self.disable_success_handler,
                      error_handler=self.generic_dbus_error_handler)

  @ExceptionForward
  def disable_success_handler(self):
    disable_elapsed = time.time() - self.disable_start
    self.assert_(disable_elapsed <
                 1.0 + self.test_args.get('async_connect_sleep_ms', 0))
    self.requirement_completed('disable')

  @ExceptionForward
  def start_get_status(self):
    # Keep on calling get_status to make sure it works at all times
    self.simple_modem.GetStatus(reply_handler=self.get_status_success_handler,
                                error_handler=self.generic_dbus_error_handler)

  @ExceptionForward
  def get_status_success_handler(self, status):
    logging.info('Got status')
    self.requirement_completed('get_status', warn_if_already_completed=False)
    gobject.timeout_add(self.status_delay_ms, self.start_get_status)

  def after_main_loop(self):
    enabled = self.modem_enabled()
    logging.info('Modem enabled: %s', enabled)
    self.assert_(enabled == 0)


class network_3GDisableWhileConnecting(test.test):
  version = 1
  def run_once(self, **kwargs):
    logging.info('setting main loop')
    dbus.mainloop.glib.DBusGMainLoop(set_as_default=True)
    self.main_loop = gobject.MainLoop()

    modem = ModemDisableTester(self, self.main_loop)

    modem.run(**kwargs)
