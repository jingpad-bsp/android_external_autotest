#!/usr/bin/python
#
# Copyright (c) 2010 The Chromium OS Authors. All rights reserved.
# Use of this source code is governed by a BSD-style license that can be
# found in the LICENSE file.

import gtk, pango
import sys

class ShowTestResults:
    _results = {}

    def __init__(self):
        for arg in sys.argv:
            if arg[0] != '-':
                self.parse_status_file(arg)

        window = gtk.Window(gtk.WINDOW_TOPLEVEL)
        window.set_name("Show Test Results")
        window.connect("destroy", lambda w: gtk.main_quit())
        window.connect('key-press-event', self.key_press_event)

        # Full screen
        screen = window.get_screen()
        screen_size = (screen.get_width(), screen.get_height())
        window.set_default_size(*screen_size)

        box = gtk.VBox()

        tests = self._results.keys()
        tests.sort()

        # Create a label of summary message
        count_all = len(tests)
        count_fail = count_all - self._results.values().count('GOOD')
        message = 'All %s tests pass!' % count_all
        if count_fail:
            message = '%s out of %s tests fail!' % (count_fail, count_all)
        message += '\nPress SPACE bar to continue.'
        label_message = self.new_label(message, color='white', size='24')
        box.pack_start(label_message, False, False, 10)

        # Create a table of test results
        table = gtk.Table(len(tests), 2)
        table.set_col_spacings(10)
        i = 0
        for test in tests:
            table.attach(self.new_label(test), 0, 1, i, i + 1)
            if self._results[test] == 'GOOD':
                table.attach(self.new_label('PASS', 'green'), 1, 2, i, i + 1)
            else:
                table.attach(self.new_label('FAIL', 'red'), 1, 2, i, i + 1)
            i = i + 1
        box.pack_start(table)

        # Put the messages center and show the scrollbar if needed.
        align = gtk.Alignment(xalign=0.5, yalign=0.5)
        align.add(box)
        viewport = gtk.Viewport()
        viewport.add(align)
        viewport.modify_bg(gtk.STATE_NORMAL, gtk.gdk.color_parse('black'))
        sw = gtk.ScrolledWindow()
        sw.set_policy(gtk.POLICY_AUTOMATIC, gtk.POLICY_AUTOMATIC)
        sw.add_with_viewport(viewport)
        sw.set_size_request(*screen_size)

        window.add(sw)
        window.show_all()


    def parse_status_file(self, status_file):
        for line in open(status_file):
            columns = line.split('\t')
            if len(columns) >= 8 and not columns[0] and not columns[1]:
                status = columns[2]
                testdir = columns[3]
                self._results[testdir] = status


    def new_label(self, text, color='light grey', size='16'):
        label = gtk.Label(text)
        label.set_alignment(0, 0)
        label.set_justify(gtk.JUSTIFY_LEFT)

        text_color = gtk.gdk.color_parse(color)
        label.modify_fg(gtk.STATE_NORMAL, text_color)
        fontdesc = pango.FontDescription('Verdana ' + size)
        label.modify_font(fontdesc)

        return label


    def key_press_event(self, widget, event):
        # Exit when space bar pressed
        if event.kayval == gtk.keysyms.space:
            sys.exit(0)
        return True


def main():
    ShowTestResults()
    gtk.main()
    return 0

if __name__ == "__main__":
    main()
