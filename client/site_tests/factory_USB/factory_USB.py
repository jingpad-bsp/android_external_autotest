# -*- coding: utf-8 -*-
#
# Copyright (c) 2011 The Chromium OS Authors. All rights reserved.
# Use of this source code is governed by a BSD-style license that can be
# found in the LICENSE file.


# DESCRIPTION :
#
# Factory test for USB ports.  The test checks USB ports are functional by
# requiring that an USB device be plugged in and unplugged from the number of
# ports specified.


import gtk
import logging
import os
import pango
import pyudev
import pyudev.glib

from autotest_lib.client.bin import test, utils
from autotest_lib.client.common_lib import error
from autotest_lib.client.cros import factory
from autotest_lib.client.cros.factory import ui as ful


_UDEV_ACTION_INSERT = 'add'
_UDEV_ACTION_REMOVE = 'remove'

_PROMPT_FMT_STR = ('Plug and unplug each USB port, {0} to go...\n'
                   '插拔每個 USB 端口, 還有 {0} 個待測試...')


class factory_USB(test.test):
    version = 1

    def usb_event_cb(self, action, device):
        if action not in [_UDEV_ACTION_INSERT, _UDEV_ACTION_REMOVE]:
          return

        factory.log('USB %s device path %s' % (action, device.device_path))
        bus_path = os.path.dirname(device.sys_path)
        bus_ver_path = os.path.join(bus_path, 'version')
        bus_version = int(float(open(bus_ver_path, 'r').read().strip()))

        if bus_version == 2:
            self._seen_usb2_paths.add(device.device_path)
        elif bus_version == 3:
            self._seen_usb3_paths.add(device.device_path)
        else:
            logging.warning('usb event for unknown bus version: %r',
                            bus_version)
            return True

        usb2_count = len(self._seen_usb2_paths)
        usb3_count = len(self._seen_usb3_paths)
        total_count = usb2_count + usb3_count

        finished = True
        if self._num_usb_ports:
          finished &= total_count >= self._num_usb_ports
        if self._num_usb2_ports:
          finished &= usb2_count >= self._num_usb2_ports
        if self._num_usb3_ports:
          finished &= usb3_count >= self._num_usb3_ports
        if finished:
            gtk.main_quit()
        else:
            txt = _PROMPT_FMT_STR.format(self._num_usb_ports - total_count)
            self._prompt.set_text(txt)

    def run_once(self,
                 num_usb_ports=None,
                 num_usb2_ports=None,
                 num_usb3_ports=None):

        assert ((num_usb_ports and (num_usb_ports > 0)) or
                (num_usb2_ports and (num_usb2_ports > 0)) or
                (num_usb3_ports and (num_usb3_ports > 0))), (
                    'USB port count not specified.')

        if not num_usb_ports:
          num_usb_ports = (num_usb2_ports or 0) + (num_usb3_ports or 0)

        self._num_usb_ports = num_usb_ports
        self._num_usb2_ports = num_usb2_ports
        self._num_usb3_ports = num_usb3_ports
        self._seen_usb2_paths = set()
        self._seen_usb3_paths = set()

        context = pyudev.Context()
        monitor = pyudev.Monitor.from_netlink(context)
        monitor.filter_by(subsystem='usb', device_type='usb_device')
        observer = pyudev.glib.GUDevMonitorObserver(monitor)
        observer.connect('device-event',
                         lambda observer, action, device: \
                                self.usb_event_cb(action, device))
        monitor.start()

        label = gtk.Label('')
        label.modify_font(pango.FontDescription('courier new condensed 20'))
        label.set_alignment(0.5, 0.5)
        label.modify_fg(gtk.STATE_NORMAL, gtk.gdk.color_parse('light green'))
        self._prompt = label
        self._prompt.set_text(_PROMPT_FMT_STR.format(self._num_usb_ports))

        vbox = gtk.VBox()
        vbox.pack_start(label, False, False)

        test_widget = gtk.EventBox()
        test_widget.modify_bg(gtk.STATE_NORMAL, gtk.gdk.color_parse('black'))
        test_widget.add(vbox)

        ful.run_test_widget(self.job, test_widget)

        factory.log('%s run_once finished' % self.__class__)
