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
import pango
import pyudev
import pyudev.glib

from autotest_lib.client.bin import test, utils
from autotest_lib.client.common_lib import error
from autotest_lib.client.cros import factory
from autotest_lib.client.cros.factory import ui as ful


_UDEV_ACTION_INSERT = 'add'
_UDEV_ACTION_REMOVE = 'remove'

_PROMPT_FMT_STR = ('插拔每個 USB 端口, 還有 {0} 個待測試...\n'
                   'Plug and unplug every USB ports, {0} to go...')


class factory_USB(test.test):
    version = 1

    def usb_event_cb(self, action, device):
        if action == _UDEV_ACTION_INSERT:
            self._plugged_devpath.add(device.device_path)
        elif action == _UDEV_ACTION_REMOVE:
            self._unplugged_devpath.add(device.device_path)
        else:
            return
        factory.log('USB %s device path %s' % (action, device.device_path))

        num_checked = len(
                self._plugged_devpath.intersection(self._unplugged_devpath))
        if num_checked >= self._num_usb_ports:
            gtk.main_quit()
        else:
            self._prompt.set_text(
                    _PROMPT_FMT_STR.format(self._num_usb_ports - num_checked))

    def run_once(self, num_usb_ports=1):
        if num_usb_ports <= 0:
            raise error.TestError('Invalid number of USB ports to check')

        self._num_usb_ports = num_usb_ports
        self._plugged_devpath = set()
        self._unplugged_devpath = set()

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
