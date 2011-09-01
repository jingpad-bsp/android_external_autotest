# Copyright (c) 2011 The Chromium OS Authors. All rights reserved.
# Use of this source code is governed by a BSD-style license that can be
# found in the LICENSE file.

from autotest_lib.client.bin import test, utils
from autotest_lib.client.common_lib import error
from autotest_lib.client.cros import backchannel, network

import logging, os, subprocess, time
import dbus

import mm


# Sample PDUs and the messages they decode into.
# TODO(njw): Add more samples with various formats, particularly
# multi-part messages.
sms_sample = [
    {'pdu' :
       '07914140540510F0040B916171056429F500001190804181106904D4F29C0E',
     'parsed' :
       {'text' : 'Test',
        'number' : '+16175046925',
        'timestamp' : '110908141801-04',
        'smsc' : '+14044550010'
        }
     },
    {'pdu' :
       ['07912160130320F8440B916171056429F5000011909161037469A0050003920201A9E5391DF43683E6EF7619C47EBBCF207A194F0789EB74D03D4D47BFEB7450D89D0791D366737A5C67D3416374581E1ED3CBF23928ED1EB3EBE43219947683E8E832A85D9ECFC3E7B20B4445A7E72077B94C9E83E86F90B80C7ADBCB72101D5D06B1CBEE331D0DA2A3E5E539FACD2683CC6F39888E2E83D8EF71980D9ABFCDF47B585E06D1DF',
        '07912160130320F5440B916171056429F50000119091610384691505000392020241E437888E2E83E670769AEE02'],
     'parsed' :
       {'text' : 'Test of some long text but without any difficult characters included in the message. '
        'This needs to be over the length threshold for the local software to do the split.',
        'number' : '+16175046925',
        'timestamp' : '110919163047-04',
        'smsc' : '+12063130028'
        }
     }
    ]

class network_ModemManagerSMS(test.test):
  version = 1

  def setup(self):
    self.job.setup_dep(['fakegudev', 'fakemodem'])

  # Create
  def create_fake_network(self):
    """Start the fakenetwork program and return the fake interface name

    Start up the fakenet program, which uses the tun driver to create
    a network device.

    Returns the name of the fake network interface.
    Sets self.fakenet_process as a handle to the process.
    """
    self.fakenet_process = subprocess.Popen(os.path.join(self.autodir,
                                                         'deps/fakemodem/bin',
                                                         'fakenet'),
                                            stdout=subprocess.PIPE)
    return self.fakenet_process.stdout.readline().rstrip()

  def create_fake_modem(self, patternfiles):
    """Start the fakemodem program and return the pty path to access it

    Start up the fakemodem program
    Argument:
    patternfiles -- List of files to read for command/response patterns

    Returns the device path of the pty that serves the fake modem, e.g.
    /dev/pts/4.
    Sets self.fakemodem_process as a handle to the process, and
    self.fakemodem as a DBus interface to it.
    """
    scriptargs = ["--patternfile=" + os.path.join(self.srcdir, x)
                  for x in patternfiles]
    name = os.path.join(self.autodir, 'deps/fakemodem/bin', 'fakemodem')
    self.fakemodem_process = subprocess.Popen(
        [os.path.join(self.autodir, 'deps/fakemodem/bin', 'fakemodem')]
        + scriptargs,
        stdout=subprocess.PIPE)
    ptyname = self.fakemodem_process.stdout.readline().rstrip()
    time.sleep(2)
    self.fakemodem = dbus.Interface(dbus.SystemBus()
                                    .get_object('org.chromium.FakeModem', '/'),
                                    'org.chromium.FakeModem')
    return ptyname

  def start_programs(self, modem_pattern_files):
    fakenetname = self.create_fake_network()
    fakemodemname = self.create_fake_modem(modem_pattern_files)
    id_props = ['property_ID_MM_CANDIDATE=1',
                'property_ID_VENDOR_ID=04e8', # Samsung USB VID
                'property_ID_MODEL_ID=6872' # Y3300 modem PID
                ]
    tty_device = (['device_file=%s' % (fakemodemname),
                   'name=%s' % (fakemodemname[5:]), # remove leading /dev/
                   'subsystem=tty',
                   'driver=fake',
                   'sysfs_path=/sys/devices/fake/tty',
                   'parent=/dev/fake-parent'] +
                  id_props)
    net_device = (['device_file=/dev/fakenet',
                   'name=%s' % (fakenetname),
                   'subsystem=net',
                   'driver=fake',
                   'sysfs_path=/sys/devices/fake/net',
                   'parent=/dev/fake-parent'] +
                  id_props)
    parent_device=['device_file=/dev/fake-parent',
                   'sysfs_path=/sys/devices/fake/parent',
                   'devtype=usb_device',
                   'subsystem=usb']
    environment = { 'FAKEGUDEV_DEVICES' : ':'.join(tty_device +
                                                   net_device +
                                                   parent_device),
                    'FAKEGUDEV_BLOCK_REAL' : 'true',
                    'LD_PRELOAD' : os.path.join(self.autodir,
                                                "deps/fakegudev/lib",
                                                "libfakegudev.so") }
    self.modemmanager = subprocess.Popen(['/usr/sbin/modem-manager',
                                          '--debug',
                                          '--log-level=DEBUG',
                                          '--log-file=/tmp/mm-log'],
                                         env=environment)
    time.sleep(3) # wait for DeviceAdded signal?
    self.modemmanager.poll()
    if self.modemmanager.returncode is not None:
      raise error.TestFail("ModemManager quit early")
    # wait for MM to stabilize?
    self.mm = mm.ModemManager(provider='org.freedesktop')
    # similarly, this would be better handled by listening for DeviceAdded,
    # but since we've blocked everything else and only supplied data for one
    # modem, it's going to be right
    self.modem_object_path = self.mm.path + '/Modems/0'

  def stop_fake_network(self):
    try:
      self.fakenet_process.poll()
      if self.fakenet_process.returncode is None:
        self.fakenet_process.terminate()
        self.fakenet_process.wait()
    except AttributeError:
      pass

  def stop_fake_modem(self):
    try:
      self.fakemodem_process.poll()
      if self.fakemodem_process.returncode is None:
        self.fakemodem_process.terminate()
        self.fakemodem_process.wait()
    except AttributeError:
      pass

  def stop_modemmanager(self):
    try:
      self.modemmanager.poll()
      if self.modemmanager.returncode is None:
        self.modemmanager.terminate()
        self.modemmanager.wait()
    except AttributeError:
      pass

  def stop_programs(self):
    self.stop_modemmanager()
    self.stop_fake_modem()
    self.stop_fake_network()



  # SMS content management - we maintain an internal model of the
  # index->PDU mapping that the fakemodem program should be returning
  # so that tests can add and remove individual PDUs and we'll handle
  # generating the correct set of responses, including the complete
  # SMS list.

  def sms_init(self):
    self.smsdict = {}
    self.fakemodem.SetResponse('\+CMGR=', '', '+CMS ERROR: 321')
    self.fakemodem.SetResponse('\+CMGD=', '', '+CMS ERROR: 321')
    self.sms_regen_list()

  def sms_remove(self, index):
    self.fakemodem.RemoveResponse('\+CMGR=%d' % (index))
    self.fakemodem.RemoveResponse('\+CMGD=%d' % (index))
    del self.smsdict[index]
    self.sms_regen_list()

  def sms_insert(self, index, pdu):
    smsc_len = int(pdu[0:1], 16)
    mlen = len(pdu)/2 - smsc_len - 1

    self.fakemodem.RemoveResponse('\+CMGD=')
    self.fakemodem.RemoveResponse('\+CMGR=')
    self.fakemodem.SetResponse('\+CMGD=%d' % (index), '', '')
    self.fakemodem.SetResponse('\+CMGR=%d' % (index),
                               '+CMGR: 1,,%d\r\n%s' % (mlen, pdu), '')
    self.fakemodem.SetResponse('\+CMGR=', '', '+CMS ERROR: 321')
    self.fakemodem.SetResponse('\+CMGD=', '', '+CMS ERROR: 321')

    self.smsdict[index] = pdu
    self.sms_regen_list()

  def sms_regen_list(self):
    response = ""
    keys = self.smsdict.keys()
    keys.sort()
    for i in keys:
      pdu = self.smsdict[i]
      smsc_len = int(pdu[0:1],16)
      mlen = len(pdu)/2 - smsc_len - 1
      response = response + "+CMGL: %d,1,,%d\r\n%s\r\n" % (i, mlen, pdu)
    self.fakemodem.SetResponse('\+CMGL=4', response, '')

  def compare(self, expected, got):
    """Compare two SMS dictionaries, discounting the index number if not specified in the first"""
    if expected == got:
      return True
    if 'index' in expected:
      return False
    if 'index' not in got:
      return False
    got = dict(got)
    del got['index']
    return expected == got

  def test_get(self, index, expected):
    try:
      sms = self.gsmsms.Get(index)
    except dbus.DBusException, db:
      if expected is not None:
        raise
      return

    if expected is None:
      raise error.TestFail("SMS.Get(%d) succeeded" % (index))
    if self.compare(expected, sms) == False:
      raise error.TestFail("SMS did not match expected values;" +
                           " got %s, expected %s" % (sms, expected))

  def test_delete(self, index, expected_success):
    try:
      self.gsmsms.Delete(index)
      if expected_success == False:
        raise error.TestFail("SMS.Delete(%d) succeeded" % (index))
    except dbus.DBusException, db:
      if expected_success:
        raise


  def compare_list(self, expected_list, got_list):
    if len(expected_list) != len(got_list):
      return False
    # There's a more Pythonic way to do this
    for (expected,got) in zip(expected_list, got_list):
      if self.compare(expected, got) == False:
        return False
    return True

  def test_list(self, expected_list):
    sms_list = self.gsmsms.List()
    if self.compare_list(expected_list, sms_list) == False:
      raise error.TestFail("SMS.List() did not match expected values;" +
                           " got %s, expected %s" % (sms_list, expected_list))


  def run_sms_test(self, testfunc, **kwargs):
    self.start_programs(modem_pattern_files=['fake-gsm', 'fake-icera'])
    self.sms_init()
    self.gsmsms = self.mm.GsmSms(self.modem_object_path)

    testfunc(**kwargs)

    self.stop_programs()

  def test_sms_has_none(self):
    self.test_list([])
    self.test_get(1, None)
    self.test_delete(1, False)
    self.test_delete(2, False)

  def test_sms_has_one(self, parsed_sms):
    self.test_list([parsed_sms])
    self.test_get(1, parsed_sms)
    self.test_get(2, None)
    self.test_delete(2, False)
    self.test_delete(1, True)

  def test_sms_one(self):
    testsms = sms_sample[0]
    self.sms_insert(1, testsms['pdu'])
    self.test_sms_has_one(testsms['parsed'])
    self.sms_remove(1)
    self.test_sms_has_none()


  def run_once(self):
    dep = 'fakegudev'
    dep_dir = os.path.join(self.autodir, 'deps', dep)
    self.job.install_pkg(dep, 'dep', dep_dir)
    dep = 'fakemodem'
    dep_dir = os.path.join(self.autodir, 'deps', dep)
    self.job.install_pkg(dep, 'dep', dep_dir)

    subprocess.check_call(["modprobe", "tun"])
    subprocess.check_call(["initctl", "stop", "modemmanager"])

    try:
      self.run_sms_test(self.test_sms_has_none)
      self.run_sms_test(self.test_sms_one)

    finally:
      # Autotest will hang if there are still children running
      self.stop_programs()
      subprocess.check_call(["initctl", "start", "modemmanager"])
      subprocess.check_call(["rmmod", "tun"])
