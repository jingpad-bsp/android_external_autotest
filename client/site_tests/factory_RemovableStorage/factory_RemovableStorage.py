# -*- coding: utf-8 -*-
#
# Copyright (c) 2012 The Chromium OS Authors. All rights reserved.
# Use of this source code is governed by a BSD-style license that can be
# found in the LICENSE file.


# DESCRIPTION :
#
# This is a factory test to test removable storage devices.
# We implement the following tests:
#   * Read/Write test
#   * Lock (write protection) test

import cairo
import gtk
import os
import pango
import pyudev
import pyudev.glib
import random
import time

from autotest_lib.client.bin import test
from autotest_lib.client.bin import utils
from autotest_lib.client.common_lib import error
from autotest_lib.client.cros import factory
from autotest_lib.client.cros.factory import task
from autotest_lib.client.cros.factory import ui


_STATE_RW_TEST_WAIT_INSERT = 1
_STATE_RW_TEST_WAIT_REMOVE = 2
_STATE_LOCKTEST_WAIT_INSERT = 3
_STATE_LOCKTEST_WAIT_REMOVE = 4

# udev constants
_UDEV_ACTION_INSERT = 'add'
_UDEV_ACTION_REMOVE = 'remove'
_UDEV_MMCBLK_PATH   = '/dev/mmcblk'
# USB card reader attributes and common text string in descriptors
_USB_CARD_ATTRS     = ['vendor', 'model', 'product', 'configuration',
                       'manufacturer']
_USB_CARD_DESCS     = ['card', 'reader']

# The GPT ( http://en.wikipedia.org/wiki/GUID_Partition_Table )
# occupies the first 34 and the last 33 512-byte blocks.
#
# We don't want to upset kernel by changing the partition table.
# Skip the first 34 and the last 33 512-byte blocks when doing
# read/write tests.
_SECTOR_SIZE = 512
_SKIP_HEAD_BLOCK = 34
_SKIP_TAIL_BLOCK = 33

# Read/Write test modes
_RW_TEST_MODE_RANDOM = 1
_RW_TEST_MODE_SEQUENTIAL = 2

_RW_TEST_INSERT_FMT_STR = lambda t: (
    '\n'.join(['insert %s drive for read/write test...' % t,
               'WARNING: DATA ON INSERTED MEDIA WILL BE LOST!\n',
               '插入%s存儲以進行讀寫測試...' % t,
               '注意: 插入裝置上的資料將會被清除!',
               ]))
_REMOVE_FMT_STR = lambda t: 'remove %s drive...\n提取%s存儲...' % (t, t)
_TESTING_FMT_STR = lambda t:'testing %s...\n%s 檢查當中...' % (t, t)
_LOCKTEST_INSERT_FMT_STR = lambda t: (
    '\n'.join(['toggle lock switch and insert %s drive again...' % t,
               '切換防寫開關並再次插入%s存儲...' % t]))
_LOCKTEST_REMOVE_FMT_STR = lambda t: (
    '\n'.join(['remove %s drive and toggle lock switch...' % t,
               '提取%s存儲並關閉防寫開關...' % t]))
_ERR_TOO_EARLY_REMOVE_FMT_STR = \
        lambda t: \
            'Device removed too early (%s).\n' \
            '太早移除外部儲存裝置 (%s).\n' % (t, t)
_ERR_TEST_FAILED_FMT_STR = lambda test_name, target_dev: (
            'IO error while running %s test on %s.\n' %
            (test_name, target_dev))
_ERR_LOCKTEST_FAILED_FMT_STR = \
        lambda target_dev: 'Locktest failed on %s.\n' % target_dev
_ERR_DEVICE_READ_ONLY_STR = \
        lambda target_dev: '%s is read-only.\n' % target_dev


class factory_RemovableStorage(test.test):
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

    def get_vidpid(self, device):
        if device is None:
            return None
        if device.device_type == 'usb_device':
            attrs = device.attributes
            if set(['idProduct', 'idVendor']) <= set(attrs.keys()):
                vidpid = attrs['idVendor'] + ':' + attrs['idProduct']
                return vidpid.strip()
        return self.get_vidpid(device.parent)

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

    def get_device_size(self, dev_path):
        try:
            dev_size = utils.system_output('blockdev --getsize64 %s' %
                                          dev_path)
        except:
            raise error.TestError('Unable to determine dev size of %s' %
                                  dev_path)

        dev_size = int(dev_size)
        if dev_size == 0:
            raise error.TestError('Unable to determine dev size of %s' %
                                  dev_path)

        gb = dev_size / 1000.0 / 1000.0 / 1000.0
        factory.log('dev size of %s : %d bytes (%.3f GB)' %
                    (dev_path, dev_size, gb))

        return dev_size

    def get_device_ro(self, dev_path):
        try:
            ro = utils.system_output('blockdev --getro %s' % dev_path)
        except:
            raise error.TestError('Unable to get RO status of %s' % dev_path)

        factory.log('%s RO : %s' % (dev_path, ro))

        return ro == '1'

    def test_read_write(self):
        self._prompt.set_text(_TESTING_FMT_STR(self._target_device))
        self._image = self.testing_image
        self._pictogram.queue_draw()
        task.schedule(self._invoke_test_read_write)

    def _invoke_test_read_write(self):
        dev_path = self._target_device
        dev_size = self.get_device_size(dev_path)
        dev_fd = None
        ok = True
        total_time_read = 0.0
        total_time_write = 0.0

        mode = [_RW_TEST_MODE_RANDOM]
        if self._has_sequential_test is True:
            mode.append(_RW_TEST_MODE_SEQUENTIAL)

        for m in mode:
            if m == _RW_TEST_MODE_RANDOM:
                # Read/Write one block each time
                bytes_to_operate = self._block_size
                loop = self._random_block_count
                factory.log('Performing r/w test on %d %d-byte random blocks' %
                            (loop, self._block_size))
            elif m == _RW_TEST_MODE_SEQUENTIAL:
                # Converts block counts into bytes
                bytes_to_operate = (self._sequential_block_count *
                                    self._block_size)
                loop = 1
                factory.log('Performing sequential r/w test of %d bytes' %
                            bytes_to_operate)

            try:
                dev_fd = os.open(dev_path, os.O_RDWR)
            except Exception as e:
                ok = False
                factory.log('Unable to open %s : %s' % (dev_path, e))

            if dev_fd is not None:
                blocks = dev_size / _SECTOR_SIZE
                # Determine the range in which the random block is selected
                random_head = _SKIP_HEAD_BLOCK
                random_tail = (blocks -
                            _SKIP_TAIL_BLOCK -
                            int(bytes_to_operate / _SECTOR_SIZE))

                if dev_size > 0x7FFFFFFF:
                # The following try...except section is for system that does
                # not have large file support enabled for Python. This is
                # typically observed on 32-bit machines. In some 32-bit
                # machines, doing seek() with an offset larger than 0x7FFFFFFF
                # (which is the largest possible value of singned int) will
                # cause OverflowError, due to failed conversion from long int
                # to int.
                    try:
                        # Test whether large file support is enabled or not.
                        os.lseek(dev_fd, 0x7FFFFFFF + 1, os.SEEK_SET)
                    except OverflowError:
                        # The system does not have large file support, so we
                        # restrict the range in which we perform the random r/w
                        # test.
                        random_tail = min(
                                    random_tail,
                                    int(0x7FFFFFFF / _SECTOR_SIZE) -
                                    int(bytes_to_operate / _SECTOR_SIZE))
                        factory.log('No large file support')

                if random_tail < random_head:
                    raise Exception('Block size too large for r/w test')

                random.seed()
                for x in xrange(loop):
                    # Select one random block as starting point.
                    random_block = random.randint(random_head, random_tail)
                    offset = random_block * _SECTOR_SIZE

                    try:
                        os.lseek(dev_fd, offset, os.SEEK_SET)
                        read_start = time.time()
                        in_block = os.read(dev_fd, bytes_to_operate)
                        read_finish = time.time()
                    except Exception as e:
                        factory.log('Failed to read block %s' % e)
                        ok = False
                        break

                    if m == _RW_TEST_MODE_RANDOM:
                        # Modify the first byte and write the whole block back.
                        out_block = chr(ord(in_block[0]) ^ 0xff) + in_block[1:]
                    elif m == _RW_TEST_MODE_SEQUENTIAL:
                        out_block = chr(0x00) * bytes_to_operate
                    try:
                        os.lseek(dev_fd, offset, os.SEEK_SET)
                        write_start = time.time()
                        os.write(dev_fd, out_block)
                        os.fsync(dev_fd)
                        write_finish = time.time()
                    except Exception as e:
                        factory.log('Failed to write block %s' % e)
                        ok = False
                        break

                    # Check if the block was actually written, and restore the
                    # original content of the block.
                    os.lseek(dev_fd, offset, os.SEEK_SET)
                    b = os.read(dev_fd, bytes_to_operate)
                    if b != out_block:
                        factory.log('Failed to write block')
                        ok = False
                        break
                    os.lseek(dev_fd, offset, os.SEEK_SET)
                    os.write(dev_fd, in_block)
                    os.fsync(dev_fd)

                    total_time_read += read_finish - read_start
                    total_time_write += write_finish - write_start

                # Make sure we close() the device file so later tests won't
                # fail.
                os.close(dev_fd)

            if ok is False:
                if self.get_device_ro(dev_path) is True:
                    factory.log('Is write protection on?')
                    self._error += _ERR_DEVICE_READ_ONLY_STR(dev_path)
                test_name = ''
                if m == _RW_TEST_MODE_RANDOM:
                    test_name = 'random r/w'
                elif m == _RW_TEST_MODE_SEQUENTIAL:
                    test_name = 'sequential r/w'
                self._error += _ERR_TEST_FAILED_FMT_STR(test_name,
                                                        self._target_device)
            else:
                if m == _RW_TEST_MODE_RANDOM:
                    factory.log('random_read_speed: %.3f MB/s' %
                        ((self._block_size * loop) / total_time_read /
                            1000 / 1000))
                    factory.log('random_write_speed: %.3f MB/s' %
                        ((self._block_size * loop) / total_time_write /
                            1000 / 1000))
                elif m == _RW_TEST_MODE_SEQUENTIAL:
                    factory.log('sequential_read_speed: %.3f MB/s' %
                                    (bytes_to_operate / total_time_read /
                                        1000 / 1000))
                    factory.log('sequential_write_speed: %.3f MB/s' %
                                    (bytes_to_operate / total_time_write /
                                        1000 / 1000))

        self._prompt.set_text(_REMOVE_FMT_STR(self._media))
        self._state = _STATE_RW_TEST_WAIT_REMOVE
        self._image = self.removal_image
        self._pictogram.queue_draw()

    def test_lock(self):
        self._prompt.set_text(_TESTING_FMT_STR(self._target_device))
        self._image = self.testing_image
        self._pictogram.queue_draw()
        task.schedule(self._invoke_test_lock)

    def _invoke_test_lock(self):
        ro = self.get_device_ro(self._target_device)

        if ro is False:
            self._error += _ERR_LOCKTEST_FAILED_FMT_STR(self._target_device)
        self._prompt.set_text(_LOCKTEST_REMOVE_FMT_STR(self._media))
        self._state = _STATE_LOCKTEST_WAIT_REMOVE
        self._image = self.locktest_removal_image
        self._pictogram.queue_draw()

    def udev_event_cb(self, action, device):
        if action == _UDEV_ACTION_INSERT:
            if self._state == _STATE_RW_TEST_WAIT_INSERT:
                if self._vidpid is None:
                    if self._media != self.get_device_type(device):
                        return True
                else:
                    device_vidpid = self.get_vidpid(device)
                    if device_vidpid not in self._vidpid:
                        return True
                    factory.log('VID:PID == %s' % self._vidpid)
                factory.log('%s device inserted : %s' %
                        (self._media, device.device_node))
                self._target_device = device.device_node
                self.test_read_write()
            elif self._state == _STATE_LOCKTEST_WAIT_INSERT:
                factory.log('%s device inserted : %s' %
                        (self._media, device.device_node))
                if self._target_device == device.device_node:
                    self.test_lock()
        elif action == _UDEV_ACTION_REMOVE:
            if self._target_device == device.device_node:
                factory.log('Device removed : %s' % device.device_node)
                if self._state == _STATE_RW_TEST_WAIT_REMOVE:
                    if self._has_locktest:
                        self._prompt.set_text(
                            _LOCKTEST_INSERT_FMT_STR(self._media))
                        self._state = _STATE_LOCKTEST_WAIT_INSERT
                        self._image = self.locktest_insertion_image
                        self._pictogram.queue_draw()
                    else:
                        gtk.main_quit()
                elif self._state == _STATE_LOCKTEST_WAIT_REMOVE:
                    gtk.main_quit()
                else:
                    self._error += _ERR_TOO_EARLY_REMOVE_RND_TEST_FMT_STR(
                            self._target_device)
                    factory.log('Device %s removed too early' %
                            self._target_device)
                    gtk.main_quit()
        return True

    def run_once(self,
                 media=None,
                 vidpid=None,
                 block_size=1024, # in bytes
                 random_block_count=3, # Number of blocks for random test
                 perform_sequential_test=False,
                 sequential_block_count=1024, # Number of blocks for seq. test
                 perform_locktest=False):

        factory.log('%s run_once' % self.__class__)

        self._error = ''
        self._target_device = None

        os.chdir(self.srcdir)

        self._media = media
        if vidpid is None:
            self._vidpid = None
        elif type(vidpid) != type(list()):
            # Convert vidpid to a list.
            self._vidpid = [vidpid]
        else:
            self._vidpid = vidpid

        self._block_size = block_size
        self._random_block_count = random_block_count
        self._has_sequential_test = perform_sequential_test
        self._sequential_block_count = sequential_block_count

        factory.log('media = %s' % media)

        self.insertion_image = cairo.ImageSurface.create_from_png(
            '%s_insert.png' % self._media)
        self.removal_image = cairo.ImageSurface.create_from_png(
            '%s_remove.png' % self._media)
        self.testing_image = cairo.ImageSurface.create_from_png(
            '%s_testing.png' % self._media)

        self._has_locktest = perform_locktest
        if perform_locktest:
            self.locktest_insertion_image = cairo.ImageSurface.create_from_png(
                '%s_locktest_insert.png' % self._media)
            self.locktest_removal_image = cairo.ImageSurface.create_from_png(
                '%s_locktest_remove.png' % self._media)

        image_size_set = set([(i.get_width(), i.get_height()) for
                              i in [self.insertion_image,
                                    self.removal_image,
                                    self.testing_image]])
        assert len(image_size_set) == 1
        image_size = image_size_set.pop()

        label = gtk.Label('')
        label.modify_font(pango.FontDescription('courier new condensed 20'))
        label.set_alignment(0.5, 0.5)
        label.modify_fg(gtk.STATE_NORMAL, gtk.gdk.color_parse('light green'))
        self._prompt = label

        self._prompt.set_text(_RW_TEST_INSERT_FMT_STR(self._media))
        self._state = _STATE_RW_TEST_WAIT_INSERT
        self._image = self.insertion_image
        context = pyudev.Context()
        monitor = pyudev.Monitor.from_netlink(context)
        monitor.filter_by(subsystem='block', device_type='disk')
        observer = pyudev.glib.GUDevMonitorObserver(monitor)
        observer.connect('device-event',
                         lambda observer, action, device: \
                                self.udev_event_cb(action, device))
        monitor.start()

        drawing_area = gtk.DrawingArea()
        drawing_area.set_size_request(*image_size)
        drawing_area.connect('expose_event', self.expose_event)
        self._pictogram = drawing_area
        hbox = gtk.HBox()
        hbox.pack_start(drawing_area, expand=True, fill=False)

        vbox = gtk.VBox()
        vbox.pack_start(hbox, False, False)
        vbox.pack_start(label, False, False)

        test_widget = gtk.EventBox()
        test_widget.modify_bg(gtk.STATE_NORMAL, gtk.gdk.color_parse('black'))
        test_widget.add(vbox)

        ui.run_test_widget(self.job, test_widget)

        if self._error:
            raise error.TestFail(self._error)

        factory.log('%s run_once finished' % self.__class__)
