# -*- coding: utf-8 -*-
#
# Copyright (c) 2010 The Chromium OS Authors. All rights reserved.
# Use of this source code is governed by a BSD-style license that can be
# found in the LICENSE file.


# DESCRIPTION :
#
# This is a factory test to test external SD and USB ports.


import cairo
import glob
import gobject
import gtk
import pango
import pyudev
import pyudev.glib
import os
import sys

from autotest_lib.client.bin import factory
from autotest_lib.client.bin import factory_ui_lib as ful
from autotest_lib.client.bin import test
from autotest_lib.client.bin import utils
from autotest_lib.client.common_lib import error


_STATE_WAIT_INSERT = 1
_STATE_WAIT_REMOVE = 2

# udev constants
_UDEV_ACTION_INSERT = 'add'
_UDEV_ACTION_REMOVE = 'remove'
_UDEV_MMCBLK_PATH   = '/dev/mmcblk'
# USB card reader attributes and common text string in descriptors
_USB_CARD_ATTRS     = ['vendor', 'model', 'product', 'configuration',
                       'manufacturer']
_USB_CARD_DESCS     = ['card', 'reader']

_INSERT_FMT_STR = lambda t: (
    '\n'.join(['insert %s drive...' % t,
               'WARNING: DATA ON INSERTED MEDIA WILL BE LOST!\n',
               '插入%s存儲...' % t,
               '注意: 插入裝置上的資料將會被清除!',
               ]))
_REMOVE_FMT_STR = lambda t: 'remove %s drive...\n提取%s存儲...' % (t, t)
_TESTING_FMT_STR = lambda t:'testing %s...\n%s 檢查當中...' % (t, t)
_ERR_TOO_EARLY_REMOVE_FMT_STR = \
        lambda t: \
            'Device removed too early (%s).\n' \
            '太早移除外部儲存裝置 (%s).\n' % (t, t)
_ERR_FIO_TEST_FAILED_FMT_STR = \
        lambda target_dev: 'IO error while running test on %s.\n' % target_dev

class factory_ExternalStorage(test.test):
    version = 1
    preserve_srcdir = True

    def expose_event(self, widget, event):
        context = widget.window.cairo_create()
        context.set_source_surface(self._image, 0, 0)
        context.paint()
        return True

    def get_attrs(self, device, key_set):
        if device is None:
            return ''
        attrs = [device.attributes[key] for key in
                    set(device.attributes.keys()) & key_set]
        attr_str = ' '.join(attrs).strip()
        if len(attr_str):
            attr_str = '/' + attr_str
        return self.get_attrs(device.parent, key_set) + attr_str

    def is_usb_cardreader(self, device):
        attr_str = self.get_attrs(device, set(_USB_CARD_ATTRS)).lower()
        for desc in _USB_CARD_DESCS:
            if desc in attr_str:
                return True
        return False


    def is_sd(self, device):
        if device.device_node.find(_UDEV_MMCBLK_PATH) == 0:
            return True
        return self.is_usb_cardreader(device)

    def get_device_type(self, device):
        if self.is_sd(device):
            return 'SD'
        return 'USB'

    def udev_event_cb(self, subtest_tag, action, device):
        if action == _UDEV_ACTION_INSERT:
            if self._state == _STATE_WAIT_INSERT:
                if self._media != self.get_device_type(device):
                    return
                factory.log('%s device inserted : %s' %
                        (self._media, device.device_node))
                self._target_device = device.device_node
                devpath = device.device_node
                self._prompt.set_text(_TESTING_FMT_STR(devpath))
                self._image = self.testing_image
                self._pictogram.queue_draw()
                gtk.main_iteration()
                result = self.job.run_test('hardware_StorageFio',
                                                 dev=devpath,
                                                 quicktest=True,
                                                 tag=subtest_tag)
                if result is not True:
                    self._error += _ERR_FIO_TEST_FAILED_FMT_STR(
                            self._target_device)
                self._prompt.set_text(_REMOVE_FMT_STR(self._media))
                self._state = _STATE_WAIT_REMOVE
                self._image = self.removal_image
                self._pictogram.queue_draw()
        elif action == _UDEV_ACTION_REMOVE:
            if self._target_device == device.device_node:
                factory.log('Device removed : %s' % device.device_node)
                if self._state != _STATE_WAIT_REMOVE:
                    self._error += _ERR_TOO_EARLY_REMOVE_FMT_STR(
                            self._target_device)
                    factory.log('Device %s removed too early' %
                            self._target_device)
                gtk.main_quit()
        return True

    def run_once(self,
                 subtest_tag=None,
                 media=None):

        factory.log('%s run_once' % self.__class__)

        self._error = ''
        self._target_device = None

        os.chdir(self.srcdir)

        self._media = media
        factory.log('media = %s' % media)

        self.insertion_image = cairo.ImageSurface.create_from_png(
            '%s_insert.png' % media)
        self.removal_image = cairo.ImageSurface.create_from_png(
            '%s_remove.png' % media)
        self.testing_image = cairo.ImageSurface.create_from_png(
            '%s_testing.png' % media)

        image_size_set = set([(i.get_width(), i.get_height()) for
                              i in [self.insertion_image,
                                    self.removal_image,
                                    self.testing_image]])
        assert len(image_size_set) == 1
        image_size = image_size_set.pop()

        factory.log('subtest_tag = %s' % subtest_tag)

        label = gtk.Label('')
        label.modify_font(pango.FontDescription('courier new condensed 20'))
        label.set_alignment(0.5, 0.5)
        label.modify_fg(gtk.STATE_NORMAL, gtk.gdk.color_parse('light green'))
        self._prompt = label

        self._prompt.set_text(_INSERT_FMT_STR(self._media))
        self._state = _STATE_WAIT_INSERT
        self._image = self.insertion_image
        self._result = False
        context = pyudev.Context()
        monitor = pyudev.Monitor.from_netlink(context)
        monitor.filter_by(subsystem='block', device_type='disk')
        observer = pyudev.glib.GUDevMonitorObserver(monitor)
        observer.connect('device-event',
                         lambda observer, action, device: \
                                self.udev_event_cb(subtest_tag, action,
                                        device))
        monitor.start()

        drawing_area = gtk.DrawingArea()
        drawing_area.set_size_request(*image_size)
        drawing_area.connect('expose_event', self.expose_event)
        self._pictogram = drawing_area

        vbox = gtk.VBox()
        vbox.pack_start(drawing_area, False, False)
        vbox.pack_start(label, False, False)

        test_widget = gtk.EventBox()
        test_widget.modify_bg(gtk.STATE_NORMAL, gtk.gdk.color_parse('black'))
        test_widget.add(vbox)

        ful.run_test_widget(self.job, test_widget)

        if self._error:
            raise error.TestFail(self._error)

        factory.log('%s run_once finished' % self.__class__)
