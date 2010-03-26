# Copyright (c) 2010 The Chromium OS Authors. All rights reserved.
# Use of this source code is governed by a BSD-style license that can be
# found in the LICENSE file.

import dbus, dbus.mainloop.glib, dbus.service, gobject, logging, re
from autotest_lib.client.bin import test
from autotest_lib.client.common_lib import error, site_ui, utils


_QUESTION_START = '''
<h5>
The Bluetooth scan discovered the following devices.<br>
If a device is not on the list, switch it into pairing mode and rescan.<br>
<br>
You can click on an input device (e.g., mouse) to pair with it.<br>
</h5>
<table border="1"><tr><td>Address</td><td>Name</td></tr>
'''

_HREF_START = '''<a href="#" onclick="do_submit('%s')">'''
_HREF_END = '''</a>'''


class Agent(dbus.service.Object):

    @dbus.service.method("org.bluez.Agent",
                         in_signature="", out_signature="")
    def Release(self):
        logging.debug("Agent: Release")


    @dbus.service.method("org.bluez.Agent",
                         in_signature="o", out_signature="s")
    def RequestPinCode(self, device):
        pin = '0000'
        logging.debug('Agent: RequestPinCode (%s), sending %s.', device, pin)
        return pin


    @dbus.service.method("org.bluez.Agent",
                         in_signature="", out_signature="")
    def Cancel(self):
        logging.debug('Agent: Cancel')


class desktopui_BluetoothSemiAuto(test.test):
    version = 1


    def handle_reply(self, device):
        logging.debug("Device created: %s", device)
        self.mainloop.quit()


    def handle_error(self, error):
        logging.debug('Unable to create device: %s', error)
        self.mainloop.quit()


    def do_connect(self, addr):
        logging.debug("do_connect: %s", addr)
        dbus.mainloop.glib.DBusGMainLoop(set_as_default=True)

        bus = dbus.SystemBus()
        manager = dbus.Interface(bus.get_object("org.bluez", "/"),
                                 "org.bluez.Manager")

        adapter = dbus.Interface(bus.get_object("org.bluez",
                                                manager.DefaultAdapter()),
                                 "org.bluez.Adapter")


        logging.debug("Creating Agent")
        agent_path = "/blueztestagent"
        try:
            agent = Agent(bus, agent_path)
        except Exception, e:
            logging.debug('Unable to create an agent: %s', e)

        self.mainloop = gobject.MainLoop()

        try:
            device = adapter.FindDevice(addr)
            adapter.RemoveDevice(device)
        except Exception, e:
            logging.debug('Unable to find/remove device %s: %s', addr, e)

        adapter.CreatePairedDevice(addr, agent_path, "DisplayOnly",
                                   reply_handler=self.handle_reply,
                                   error_handler=self.handle_error)

        logging.debug('Starting mainloop...')
        self.mainloop.run()
        logging.debug('... mainloop ended.')

        device = adapter.FindDevice(addr)
        input = dbus.Interface(bus.get_object("org.bluez", device),
                               "org.bluez.Input")
        input.Connect()
        logging.debug('Connected to input:%s.', addr)


    def run_once(self, timeout=60):
        question_prepend = ''
        while True:
            question = question_prepend + _QUESTION_START
            hciscan = utils.system_output('hcitool scan')
            logging.debug(hciscan)
            for line in hciscan.split('\n'):
                line = line.strip()
                match = re.search(r'^(..:..:..:..:..:..)\s+(.*)$', line)
                if match:
                    addr = match.group(1)
                    question += '<tr>'
                    question += ('<td>' +
                                 (_HREF_START % addr) + addr + _HREF_END +
                                 '</td>')
                    question += '<td>' + match.group(2) + '</td>'
                    question += '</tr>'
            question += '</table><br>'

            dialog = site_ui.Dialog(question=question,
                                    choices=['Pass', 'Fail', 'Rescan'])
            result = dialog.get_result()
            if result is None:
                raise error.TestFail('Timeout')
            if result == 'Pass':
                return
            if result == 'Fail':
                raise error.TestFail('Unable to find Bluetooth devices')
            if result == 'Rescan':
                question_prepend = ''
                continue

            logging.debug("Connecting to %s", result)
            try:
                self.do_connect(result)
                question_prepend = 'Paired with device %s.<br>' % result
            except Exception, e:
                logging.debug('Unable to connect: %s', e)
                question_prepend = 'Unable to pair with device %s.<br>' % result
