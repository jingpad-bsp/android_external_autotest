#!/usr/bin/python

# Copyright (c) 2011 The Chromium OS Authors. All rights reserved.
# Use of this source code is governed by a BSD-style license that can be
# found in the LICENSE file.

"""Connect to a WiFi service and report the amount of time it took

This script initiates a connection to a WiFi service and reports
the time to major state changes (assoc, config).  If the connection
fails within the desired time, it outputs the contents of the log
files during that intervening time.

"""

import dbus
import gobject
import logging
import optparse
import sys
import time
import traceback

# Once these are no longer copied to DUTs manually, this should become
# from autotest_lib.client.common_lib.cros.site_wlan import constants
import constants

from site_wlan_wait_state import *

CONNECTION_MANAGER_ERROR = constants.CONNECTION_MANAGER + '.Error'
ERROR_INPROGRESS = CONNECTION_MANAGER_ERROR + '.InProgress'
ERROR_UNKNOWNMETHOD = CONNECTION_MANAGER_ERROR + '.UnknownMethod'
ERROR_ALREADYCONNECTED = CONNECTION_MANAGER_ERROR + '.AlreadyConnected'
connect_quirks = {}

def convert_dbus_value(value):
    if value.__class__ == dbus.Byte:
        return int(value)
    elif value.__class__ == dbus.Boolean:
        return bool(value)
    else:
        return value


class ConnectStateHandler(StateHandler):
  def __init__(self, dbus_bus, connection_settings, hidden, timeout,
               start_time=None, debug=False, scan_retry=8):
    self.connection_settings = connection_settings
    self.acquisition_time = None
    self.authentication_time = None
    self.configuration_time = None
    self.frequency = 0
    self.hidden = hidden
    self.phymode = None
    self.security = None
    self.service_handle = None
    self.scan_timeout = None
    self.scan_retry = scan_retry
    StateHandler.__init__(self, dbus_bus,
                          [(connection_settings['SSID'], 'State', 'ready',
                            False, True)],
                          timeout, None, timeout, debug)
    if start_time:
      self.run_start_time = start_time

    self.bus.add_signal_receiver(
        self.SupplicantChangeCallback,
        signal_name='PropertiesChanged',
        dbus_interface=constants.SUPPLICANT_INTERFACE)


  def _GetMatchedService(self, service_list):
    """Get a service matching the connection setting from a list of services.

    Args:
      service_list: An array of (1) DBus objects for Services with a specified
        ssid.

    Returns:
      The DBus object for the service that matches our connection_settings
      (None if nothing matched).
    """
    matched_service = None
    for svc in service_list:
      props = svc.GetProperties()
      set_props = {}
      for key, val in self.connection_settings.items():
        prop_val = convert_dbus_value(props.get(key))
        if key != 'SSID' and  prop_val != val:
          if key == "EAP.UseSystemCAs":
            set_props[key] = bool(val)
          elif (key in ['Passphrase', 'SaveCredentials'] or
              key.startswith('EAP.')):
            set_props[key] = val
          elif (key == "Security" and
                val in ['wpa', 'rsn'] and
                str(prop_val) == 'psk'):
            # The service entry doesn't differentiate between WPA types before
            # association.
            pass
          else:
            self.Debug(
                'Service key mismatch: %s (desired "%s" != available "%s")' %
                (key, val, str(prop_val)))
            break
      else:
        for key, val in set_props.iteritems():
          try:
            self.Debug('Setting property %s to %s' % (key, val))
            svc.SetProperty(key, val)
          except dbus.exceptions.DBusException, e:
            self.failure = ('SetProperty: DBus exception %s for set of %s' %
                            (e, key))
            raise e

        matched_service = svc
        if self.scan_timeout is not None:
          gobject.source_remove(self.scan_timeout)
          self.scan_timeout = None
    return matched_service


  def FindService(self, path_list=None):
    service = None
    try:
      service = self._GetMatchedService(
         FindObjects('Service', 'SSID', self.service_name,
                      path_list=path_list))
    except dbus.exceptions.DBusException, e:
      # Failure reason must have been set by _GetMatchedService().
      return None

    if not service and self.hidden:
      try:
        path = manager.GetService(
            dbus.Dictionary(self.connection_settings, signature='sv'))
        service = dbus.Interface(
            self.bus.get_object(constants.CONNECTION_MANAGER, path),
            constants.CONNECTION_MANAGER_SERVICE)
      except dbus.exceptions.DBusException, e:
        self.failure = ('GetService: DBus exception %s for settings %s' %
                        (e, self.connection_settings))
        return None
    elif not service and not self.scan_timeout:
      self.DoScan()
      return None
    elif not service:
      return None

    if not self.acquisition_time:
      self.acquisition_time = time.time()

    # If service isn't already connecting or connected, start now
    if (service.GetProperties()['State'] not in
        ('association', 'configuration', 'ready')):
      try:
        service.Connect()
      except dbus.exceptions.DBusException, e:
        if e.get_dbus_name() == ERROR_INPROGRESS:
          self.Debug('Service was already in progress (state=%s)' %
                     service.GetProperties().get('State'))
          connect_quirks['in_progress'] = 1
        else:
          print 'FAIL(acquire): DBus exception in Connect() %s' % e
          ErrExit(2)
    else:
      self.Debug("skipping Connect call, service is in %s state" %
                 service.GetProperties()['State'])

    self.service_handle = service
    return service

  def DoScan(self):
    self.scan_timeout = None
    self.Debug('Service not found; requesting scan...')
    try:
      manager.RequestScan('wifi')
    except dbus.exceptions.DBusException, e:
      if e.get_dbus_name() != ERROR_INPROGRESS:
        raise
    self.scan_timeout = gobject.timeout_add(int(self.scan_retry*1000),
                                                  self.DoScan)

  def StateChanged(self):
    # If we entered the "configuration" state, mark that down
    if self.svc_state == 'configuration':
      self.configuration_time = time.time()
    # NB: do this on all changes in case configuration is skipped
    props = self.service_handle.GetProperties()
    self.security = props.get('Security', None)
    self.frequency = props.get('WiFi.Frequency', 0)
    self.phymode = props.get('WiFi.PhyMode', None)

  def Stage(self):
    if not self.wait_path:
      return 'acquire'
    elif not self.configuration_time:
      return 'assoc'
    else:
      return 'config'

  def SupplicantChangeCallback(self, args, **kwargs):
    if 'State' in args:
      state = args['State']
      self.Debug('Supplicant state is \'%s\'' % state)
      if (not self.authentication_time and
          (state == 'authenticating' or state == 'associating')):
        self.authentication_time = time.time()
      elif state == 'inactive' or state == 'disconnected':
        self.authentication_time = None


def ErrExit(code):
  try:
    handler.service_handle.Disconnect()
  except:
    pass
  DumpLogs(logs)
  sys.exit(code)


def split_psk(settings, psk):
  cert_args = psk.split(':')
  for i in xrange(0, len(cert_args), 2):
    settings[cert_args[i]] = cert_args[i+1]


def main(argv):
  parser = optparse.OptionParser('Usage: %prog [options...] '
                                 'ssid security psk assoc_timeout cfg_timeout')
  parser.add_option('--hidden', dest='hidden', action='store_true',
                    help='This is a hidden network')
  parser.add_option('--debug', dest='debug', action='store_true',
                    help='Report state changes and other debug info')
  parser.add_option('--mode', dest='mode', default='managed',
                    help='AP mode')
  parser.add_option('--nosave', dest='save_creds', action='store_false',
                    default=True, help='Do not save credentials')
  (options, args) = parser.parse_args(argv[1:])

  if len(argv) <= 4:
    parser.error('Required arguments: ssid security psk assoc_timeout '
                 'config_timeout')

  ssid           = args[0]
  security       = args[1]
  psk            = args[2]
  assoc_timeout  = float(args[3])
  config_timeout = float(args[4])

  connection_settings = {
      'Type': 'wifi',
      'Mode': options.mode,
      'SSID': ssid,
      'SaveCredentials' : options.save_creds
  }

  if security:
    connection_settings['Security'] = security

  if security == '802_1x':
    split_psk(connection_settings, psk)
  elif security == '802_1x_wep':
    split_psk(connection_settings, psk)
    connection_settings['Security'] = 'wep'
  elif security in ['wep', 'wpa', 'rsn', 'psk']:
    connection_settings['Passphrase'] = psk

  global logs
  global handler
  logs = OpenLogs('/var/log/messages', '/var/log/net.log')

  assoc_start = time.time()
  handler = ConnectStateHandler(bus, connection_settings, options.hidden,
                                assoc_timeout, assoc_start, options.debug)
  try:
    if handler.NextState():
      handler.RunLoop()
  except dbus.exceptions.DBusException, e:
    if e.get_dbus_name() == ERROR_INPROGRESS:
      connect_quirks['in_progress'] = 1
      print>>sys.stderr, 'Previous connect is still in progress!'
    if e.get_dbus_name() == ERROR_UNKNOWNMETHOD:
      connect_quirks['lost_dbus_connect'] = 1
      print>>sys.stderr, 'Lost the service handle during Connect()!'
    if e.get_dbus_name() != ERROR_ALREADYCONNECTED:
      print 'FAIL(%s): ssid %s DBus exception %s' % (handler.Stage(), ssid, e)
      ErrExit(2)
  except Exception, e:
    print 'FAIL(%s): ssid %s exception %s' % (handler.Stage(), ssid, e)
    traceback.print_exc(file=sys.stderr)
    ErrExit(2)
  if handler.Failure():
    print 'FAIL(%s): ssid %s %s' % (handler.Stage(), ssid, handler.Failure())
    ErrExit(2)

  end = time.time()
  config_start = handler.configuration_time
  acq_start = handler.acquisition_time
  if acq_start:
    acquire_time = acq_start - assoc_start
    assoc_start = acq_start
  else:
    acquire_time = 0.0
  auth_start = handler.authentication_time
  if auth_start:
    wpa_select_time = auth_start - assoc_start
    assoc_start = auth_start
    # auth_start and assoc_start are timestamps coming from two different
    # processes, and when they are close, auth_start can occur before
    # assoc_start, resulting in a negative wpa_select_time.  In this case, set
    # wpa_select_time to zero.
    if wpa_select_time < 0:
      wpa_select_time = 0.0
  else:
    wpa_select_time = 0.0
  if config_start:
    config_time = end - config_start
    if config_time < 0.0:
      config_time = 0.0
    assoc_time = config_start - assoc_start
    if assoc_time < 0.0:
      assoc_time = 0.0
  else:
    config_time = 0.0
    assoc_time = end - assoc_start
  if not handler.Success():
    print ('TIMEOUT(%s): ssid %s acquire %3.3f wpa_select %3.3f assoc %3.3f '
           'config %3.3f secs state %s' %
           (handler.Stage(), ssid, acquire_time, wpa_select_time, assoc_time,
            config_time,
            handler.svc_state))
    ErrExit(3)

  print ('OK %3.3f %3.3f %3.3f %3.3f %d %s %s %s '
         '(acquire wpa_select assoc and config times in sec, quirks)' %
         (acquire_time, wpa_select_time, assoc_time, config_time,
          handler.frequency, handler.phymode, handler.security,
          str(connect_quirks.keys())))

  if connect_quirks:
    DumpLogs(logs)
  sys.exit(0)

if __name__ == '__main__':
  main(sys.argv)
