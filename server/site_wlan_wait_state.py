#!/usr/bin/python

"""Wait for a series of SSID state transitions.

Accepts a list of ServiceName=State pairs and waits for each transition to
occur.

This provides a means for laying out a series of service state
transitions we expect to happen.  The script runs and finds each
individual service (by default it also waits for the service to
actually come into existence) and then waits for the servive state
to transition to the desired state.  The script then moves on to
the next transition.

On success, a list that is as long as the input transitions is
returned, each with the number of seconds it took for each transiton
to occur.  On failure, the last element will be a string containing
"ERR_..." which is the error that caused this state transition to
have failed.
"""

import optparse
import sys
import time
import dbus
import dbus.mainloop.glib
import gobject
import subprocess

FLIMFLAM = 'org.chromium.flimflam'

bus_loop = dbus.mainloop.glib.DBusGMainLoop(set_as_default=True)
bus = dbus.SystemBus(mainloop=bus_loop)
manager = dbus.Interface(bus.get_object(FLIMFLAM, '/'), FLIMFLAM + '.Manager')


def GetObject(kind, path):
  return dbus.Interface(bus.get_object(FLIMFLAM, path), FLIMFLAM + '.' + kind)

def GetObjectList(kind, path_list):
  if not path_list:
    path_list = manager.GetProperties().get(kind + 's', [])
  return [GetObject(kind, path) for path in path_list]


def PrintProperties(item):
  print>>sys.stderr, '[ %s ]' % (item.object_path)
  for key, val in item.GetProperties().items():
    print>>sys.stderr, '    %s = %s' % (key, str(val))


# Open each log file and seek to the current end
def OpenLogs(*logfiles):
  logs = []
  for logfile in logfiles:
    try:
      msgs = open(logfile)
      msgs.seek(0, 2)
      logs.append({ 'name': logfile, 'file': msgs })
    except Exception, e:
      # If we cannot open the file, this is not necessarily an error
      pass

  return logs


def DumpObjectList(kind):
  print>>sys.stderr, '%s list:' % kind
  for item in GetObjectList(kind, None):
    PrintProperties(item)


# Returns the list of the wifi interfaces (e.g. "wlan0") known to flimflam
def GetWifiInterfaces():
  interfaces = []
  device_paths = manager.GetProperties().get('Devices', None)
  for device_path in device_paths:
    device = dbus.Interface(
      bus.get_object('org.chromium.flimflam', device_path),
      'org.chromium.flimflam.Device')
    props = device.GetProperties()
    type = props.get('Type', None)
    interface = props.get('Interface', None)
    if type == 'wifi':
      interfaces.append(interface)
  return interfaces


def DumpLogs(logs):
  for log in logs:
    print>>sys.stderr, 'Content of %s during our run:' % log['name']
    print>>sys.stderr, '  )))  '.join(log['file'].readlines())

  for interface in GetWifiInterfaces():
    print>>sys.stderr, 'iw dev %s scan output: %s' % \
        ( interface,
          subprocess.Popen(['iw', 'dev', interface, 'scan', 'dump'],
                           stdout=subprocess.PIPE).communicate()[0])

  DumpObjectList('Service')


def GetObjectProperty(kind, attr, props):
  if attr == 'SSID' and kind == 'Service':
    # Special case: Services don't actually have an "SSID" property
    if 'WiFi.HexSSID' in props:
      # Use the Service's hex WiFi.HexSSID property to generate a raw string
      hex_ssid = props['WiFi.HexSSID']
      return ''.join([chr(int(hex_ssid[offset:offset+2], 16))
                      for offset in range(0, len(hex_ssid), 2)])
    # Use the Service's name
    return str(props.get('Name'))
  return props.get(attr)


def FindObjects(kind, attr, val, path_list=None, cache=None):
  """Find an object in the manager of type _kind_ with _attr_ set to _val_."""

  if cache is None:
    cache = {}

  ret = []
  if val in cache:
    return cache[val]

  values = cache.values()
  for obj in GetObjectList(kind, path_list):
    if obj in values:
      continue
    try:
      props = obj.GetProperties()
    except dbus.exceptions.DBusException, e:
      print>>sys.stderr, ('Got exception %s while getting props on %s' %
                          (e.get_dbus_name() , obj))
      continue
    objval = GetObjectProperty(kind, attr, props)
    if objval:
      if not objval in cache:
        cache[objval] = [obj]
      else:
        cache[objval].append(obj)
      if objval == val:
        ret.append(obj)
  return ret

class StateHandler(object):
  """Listens for state transitions."""

  def __init__(self, dbus_bus, in_state_list, run_timeout, step_timeout=None,
               svc_timeout=None, debug=False):
    self.bus = dbus_bus
    self.state_list = list(in_state_list)
    self.run_timeout = run_timeout
    if step_timeout is None:
      self.step_timeout = run_timeout
    else:
      self.step_timeout = step_timeout
    if svc_timeout is None:
      self.svc_timeout = self.step_timeout
    else:
      self.svc_timeout = svc_timeout
    self.debug = debug
    self.waiting_paths = {}
    self.run_start_time = None
    self.step_start_time = None
    self.event_timeout_ptr = None
    self.wait_path = None
    self.wait_state = None
    self.waiting_for_services = False
    self.results = []
    self.service_cache = {}
    self.svc_state = None
    self.failure = False

  def Debug(self, debugstr):
    if self.debug:
      elapsed_time = time.time() - self.step_start_time
      print>>sys.stderr, '[%8.3f] %s' % (elapsed_time, debugstr)

  def StateChangeCallback(self, attr, value, **kwargs):
    """State change callback handle: did we enter the desired state?"""

    if str(attr) != 'State':
      if str(attr) == 'Strength':
        value = int(value)
      self.Debug('Received signal (%s=%s)' % (str(attr), str(value)))
      return

    state = str(value)

    if not 'path' in kwargs:
      self.Debug('Cannot get path out of args passed to StateChangeCB')
      self.runloop.quit()

    if str(kwargs['path']) != self.wait_path:
      self.Debug('Path %s is not expected %s' %
                 (kwargs['path'], self.wait_path))
      return

    self.svc_state = state
    self.Debug('Service %s changed state: %s' %
               (repr(self.service_name), state))

    if state == self.wait_state:
      self.results.append('%.3f' % (time.time() - self.step_start_time))
      if not self.NextState():
        self.runloop.quit()
    else:
      self.StateChanged()

  def StateChanged(self):
    pass

  def ServicesChangeCallback(self, attr, value):
    """Each time service list changes, check to see if we find our service."""

    if self.wait_path:
      # Not interested -- we already have our service handle
      return

    if str(attr) != 'Services':
      # Not interested -- this is not a change to "Services"
      return

    svc = self.FindService(value)
    if svc:
      self.Debug('Service %s added to service list' % repr(self.service_name))
      self.CancelTimeout()
      elapsed_time = time.time() - self.step_start_time
      if self.WaitForState(svc, self.step_timeout - elapsed_time):
        self.results.append('%.3f' % elapsed_time)
        return self.NextState()
    elif self.failure:
      self.results.append('ERR_FAILURE')
      self.runloop.quit()

  def FindService(self, path_list=None):
    ret = FindObjects('Service', 'Name', self.service_name,
                       path_list=path_list, cache=self.service_cache)
    if len(ret):
      return ret[0]
    return None


  def NextState(self):
    """Set up a timer for the next desired state transition."""

    self.CancelTimeout()

    if not self.state_list:
      return False

    self.service_name, self.wait_state = self.state_list.pop(0)
    if self.wait_state.startswith('+'):
      self.wait_state = self.wait_state[1:]
      self.waitchange = True
    else:
      self.waitchange = False

    now = time.time()
    if self.run_start_time is None:
      self.run_start_time = now
    elapsed_time = time.time() - self.run_start_time
    self.step_timeout = min(self.step_timeout,
                            self.run_timeout - elapsed_time)
    self.step_start_time = now

    # Find a service that matches this ssid
    svc = self.FindService()
    if not svc:
      if self.failure:
        self.results.append('ERR_FAILURE')
        return False
      elif self.svc_timeout <= 0:
        self.results.append('ERR_NOTFOUND')
        return False
      self.WaitForService(min(self.svc_timeout, self.step_timeout))
    else:
      if self.WaitForState(svc, self.step_timeout):
        self.results.append('0.0')
        return self.NextState()

    return True

  def WaitForService(self, wait_time):
    """Setup a callback for changes to the service list."""

    self.svc_state = None
    self.wait_path = None

    if not self.waiting_for_services:
      self.waiting_for_services = True
      self.bus.add_signal_receiver(self.ServicesChangeCallback,
                                   signal_name='PropertyChanged',
                                   dbus_interface=FLIMFLAM+'.Manager',
                                   path='/')

    self.StartTimeout(wait_time)

  def WaitForState(self, svc, wait_time):
    """Setup a callback for state changes on our service."""

    # Are we already in the desired state?
    self.svc_state = svc.GetProperties().get('State')
    self.wait_path = svc.object_path

    self.StateChanged()

    if self.svc_state == self.wait_state and not self.waitchange:
      return True

    if not self.wait_path in self.waiting_paths:
      self.waiting_paths[self.wait_path] = True
      self.bus.add_signal_receiver(self.StateChangeCallback,
                                   signal_name='PropertyChanged',
                                   dbus_interface=FLIMFLAM+'.Service',
                                   path=self.wait_path,
                                   path_keyword='path')

    self.StartTimeout(wait_time)

  def StartTimeout(self, wait_time):
    if wait_time <= 0:
      self.HandleTimeout()
    else:
      self.event_timeout_ptr = gobject.timeout_add(int(wait_time*1000),
                                                   self.HandleTimeout)

  def CancelTimeout(self):
    if self.event_timeout_ptr is not None:
      gobject.source_remove(self.event_timeout_ptr)
      self.event_timeout_ptr = None

  def HandleTimeout(self):
    if self.svc_state:
      self.results.append('ERR_TIMEDOUT=' + self.svc_state)
    else:
      self.results.append('ERR_NOTFOUND')
    self.runloop.quit()

  def PrintSummary(self):
    print ' '.join(map(str, self.results))

  def RunLoop(self):
    self.runloop = gobject.MainLoop()
    self.runloop.run()

  def Success(self):
    if self.state_list or (self.results and self.results[-1].startswith('ERR')):
      return False
    return True

  def Failure(self):
    return self.failure

def main(argv):
  parser = optparse.OptionParser('Usage: %prog [options...] [SSID=state...]')
  parser.add_option('--run_timeout', dest='run_timeout', type='int', default=10,
                    help='Maximum time for sequence of state changes to occur')
  parser.add_option('--step_timeout', dest='step_timeout', type='int',
                    help='Maximum time for a single state change to occur')
  parser.add_option('--svc_timeout', dest='svc_timeout', type='int',
                    help='Maximum time to wait for service to exist')
  parser.add_option('--debug', dest='debug', action='store_true',
                    help='Show debug info')
  (options, args) = parser.parse_args(argv[1:])

  state_list = []
  for arg in args:
    name, sep, desired_state = arg.partition('=')
    if sep != '=' or not desired_state:
      parser.error('Invalid argument %s; arguments should be of the form '
                   '"SSID=STATE..."' % arg)

    state_list.append((name, desired_state))

  handler = StateHandler(bus, state_list, options.run_timeout,
                         options.step_timeout, options.svc_timeout,
                         options.debug)

  logs = OpenLogs('/var/log/messages')
  if handler.NextState():
    handler.RunLoop()

  handler.PrintSummary()

  if not handler.Success():
    DumpLogs(logs)
    sys.exit(1)

  sys.exit(0)

if __name__ == '__main__':
  main(sys.argv)
