# Copyright (c) 2012 The Chromium OS Authors. All rights reserved.
# Use of this source code is governed by a BSD-style license that can be
# found in the LICENSE file.

import gtk
import os
from autotest_lib.client.cros import factory
from autotest_lib.client.cros.factory import ui as ful
from autotest_lib.client.cros.factory import gooftools


class SelectHwidTask(object):

    SELECTION_PER_PAGE = 10
    HWID_AUTODETECT = None

    def __init__(self, data):
        self.data = data

    def build_hwid_list(self):
        with os.popen("crossystem hwid 2>/dev/null", "r") as p:
            current_hwid = p.read().strip()

        (stdout, _, result) = gooftools.run("hwid_tool.py list_hwids",
                                            ignore_status=True)

        known_list = stdout.splitlines()
        if (not known_list) or (result != 0):
            factory.log('Warning: No valid HWID database in system.')
            known_list = []

        # Build a list with elements in (display_text, hwid_value).
        # The first element is "current value".
        hwids = [('<Current Value> %s' % current_hwid, current_hwid)]
        hwids += [(hwid, hwid) for hwid in known_list]
        return hwids

    def key_press_callback(self, widget, event):
        # Process page navigation
        KEY_PREV = [65361, 65362, ord('h'), ord('k')]  # Left, Up
        KEY_NEXT = [65363, 65364, ord('l'), ord('j')]  # Right, Down
        if event.keyval in KEY_PREV:
            if self.page_index > 0:
                self.page_index -= 1
            self.render_page()
            return True
        if event.keyval in KEY_NEXT:
            if self.page_index < self.pages - 1:
                self.page_index += 1
            self.render_page()
            return True

        char = chr(event.keyval) if event.keyval in range(32, 127) else None
        factory.log('key_press %s(%s)' % (event.keyval, char))
        try:
            select = int(char)
        except ValueError:
            factory.log('Need a number.')
            return True

        select = select + self.page_index * self.SELECTION_PER_PAGE
        if select < 0 or select >= len(self.hwid_list):
            factory.log('Invalid selection: %d' % select)
            return True

        data = self.hwid_list[select]
        hwid = data[1]
        factory.log('Selected: %s' % ', '.join(data).replace('\n', ' '))

        self.label.set_text('Checking selected HWID [%s]...' % hwid)
        gtk.main_iteration(False)  # try to update screen
        # TODO(tammo) Use hwid_tool or probe to quick probe if selected HWID
        # matches current system, by checking non-firmware components.

        self.data['hwid'] = hwid
        self.stop()
        return True

    def register_callbacks(self, window):
        window.connect('key-press-event', self.key_press_callback)
        window.add_events(gtk.gdk.KEY_PRESS_MASK)

    def render_page(self):
        msg = 'Choose a HWID:\n\n'
        start = self.page_index * self.SELECTION_PER_PAGE
        end = start + self.SELECTION_PER_PAGE
        for index, data in enumerate(self.hwid_list[start:end]):
            msg += '%s) %s\n\n' % (index, data[0])
        if self.pages > 1:
            msg += '[Page %d / %d, navigate with arrow keys]' % (
                    self.page_index + 1, self.pages)
        self.label.set_text(msg)

    def start(self, window, container, on_stop):
        self.on_stop = on_stop
        self.container = container

        self.page_index = 0
        self.pages = 0

        self.hwid_list = self.build_hwid_list()
        self.pages = len(self.hwid_list) / self.SELECTION_PER_PAGE
        if len(self.hwid_list) % self.SELECTION_PER_PAGE:
            self.pages += 1

        self.label = ful.make_label('')
        widget = gtk.EventBox()
        widget.modify_bg(gtk.STATE_NORMAL, ful.BLACK)
        widget.add(self.label)
        self.render_page()

        self.callback = (window, window.connect('key-press-event',
                                                self.key_press_callback))
        window.add_events(gtk.gdk.KEY_PRESS_MASK)

        self.widget = widget
        container.add(widget)
        container.show_all()

    def stop(self):
        (window, callback_id) = self.callback
        window.disconnect(callback_id)
        self.container.remove(self.widget)
        self.on_stop(self)
