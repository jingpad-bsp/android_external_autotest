# Copyright (c) 2010 The Chromium OS Authors. All rights reserved.
# Use of this source code is governed by a BSD-style license that can be
# found in the LICENSE file.

import dbus, dbus.mainloop.glib, dbus.service, gobject, logging, re
from autotest_lib.client.bin import utils
from autotest_lib.client.common_lib import error
from autotest_lib.client.cros import cros_ui_test, ui


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


class hardware_BluetoothSemiAuto(cros_ui_test.UITest):
    version = 1


    def initialize(self, creds = '$default'):
        cros_ui_test.UITest.initialize(self, creds)


    def cleanup(self):
        cros_ui_test.UITest.cleanup(self)
        self.disconnect_all()


    def handle_reply(self, device):
        logging.debug("Device created: %s", device)
        self.mainloop.quit()


    def handle_error(self, error):
        logging.debug('Unable to create device: %s', error)
        self.mainloop.quit()


    def get_bus_adapter(self):
        bus = dbus.SystemBus()
        manager = dbus.Interface(bus.get_object("org.bluez", "/"),
                                 "org.bluez.Manager")

        adapter = dbus.Interface(bus.get_object("org.bluez",
                                                manager.DefaultAdapter()),
                                 "org.bluez.Adapter")
        return (bus, adapter)

    def do_connect(self, addr):
        logging.debug("do_connect: %s", addr)
        dbus.mainloop.glib.DBusGMainLoop(set_as_default=True)

        pin_required = addr.endswith('p')
        if pin_required:
            addr = addr[:-1]

        bus, adapter = self.get_bus_adapter()

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

        if pin_required:
            # The user will have to enter the pin code on the keyboard. The
            # code must be entered after the discovery process starts. The
            # problem is that the Agent class defined above does not provide
            # enough flexibility to allow the caller to do something after
            # pairing started but before it has been completed or timed out.
            # This point in time is the closest to the pairing process start.
            # So we ask the user to enter the pin code 5 seconds after this
            # page closes: pairing starts right after that and 5 seconds is
            # enough for the process to be ready to accept user input.
            question = 'Enter pin code "0000" on the BT keyboard '
            question += 'at least 5 secs after this page closes'
            dialog = ui.Dialog(question=question, choices=[],
                               checkboxes=[], textinputs=[], timeout=5)
            dialog.get_entries()
        self.mainloop.run()
        logging.debug('... mainloop ended.')

        device = adapter.FindDevice(addr)
        input = dbus.Interface(bus.get_object("org.bluez", device),
                               "org.bluez.Input")
        input.Connect()
        logging.debug('Connected to input:%s.', addr)

    def disconnect_all(self):
        logging.debug('disconnect_all')
        _, adapter = self.get_bus_adapter()

        for dev in list(adapter.ListDevices()):
            logging.debug('disconnecting %s' % dev)
            adapter.RemoveDevice(dev)


    def run_once(self):
        question_prepend = ''
        checkboxes = ['BT Mouse', 'Built In Mouse']
        textinputs = ['BT Keyboard', 'Built In Keyboard']
        while True:
            question = question_prepend + _QUESTION_START
            hciscan = utils.system_output('hcitool scan')
            logging.debug(hciscan)
            for line in hciscan.split('\n'):
                line = line.strip()
                match = re.search(r'^(..:..:..:..:..:..)\s+(.*)$', line)
                if match:
                    addr = match.group(1)
                    if 'keyboard' in line.lower():
                        addr += 'p'  # Pin's required
                    question += '<tr>'
                    question += ('<td>' +
                                 (_HREF_START % addr) + addr + _HREF_END +
                                 '</td>')
                    question += '<td>' + match.group(2) + '</td>'
                    question += '</tr>'
            question += '</table><br>'

            dialog = ui.Dialog(question=question, choices=['Done', 'Rescan'],
                               checkboxes=checkboxes, textinputs=textinputs)
            form_entries = dialog.get_entries()
            if not form_entries:
                raise error.TestFail('Timeout')
            result = form_entries['result']
            if result == 'Rescan':
                question_prepend = ''
                continue
            elif result == 'Done':
                self.process_form_entries(form_entries, checkboxes, textinputs)
                return

            logging.debug("Connecting to %s", result)
            try:
                self.do_connect(result)
                question_prepend = 'Paired with device %s.<br>' % result
            except Exception, e:
                logging.debug('Unable to connect: %s', e)
                question_prepend = 'Unable to pair with device %s.<br>' % result


    def process_form_entries(self, form_entries, checkboxes, textinputs):
        bt_errors = []
        for check in checkboxes:
            if form_entries.get(check) != 'on':
                bt_errors.append('"%s" not checked' % check)
        for text in textinputs:
            if not form_entries.get(text):
                bt_errors.append('no input in "%s" field' % text)
        if bt_errors:
            raise error.TestFail('Bluetooth input errors:\n%s' %
                                 '\n'.join(bt_errors))
