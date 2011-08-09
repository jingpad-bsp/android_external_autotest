# Copyright (c) 2011 The Chromium OS Authors. All rights reserved.
# Use of this source code is governed by a BSD-style license that can be
# found in the LICENSE file.

import glob
import gtk
import os
import re
from gtk import gdk

from autotest_lib.client.bin import factory
from autotest_lib.client.bin import factory_ui_lib as ful
from autotest_lib.client.bin import test
from autotest_lib.client.common_lib import error
from autotest_lib.client.cros import gooftools


class factory_ProbeHWID(test.test):
    version = 4
    SELECTION_PER_PAGE = 10
    HWID_AUTODETECT = None

    def probe_hwid(self):
        """ Finds out the matching HWID by detection.
            This function must not use any GUI resources.
        """
        command = 'gooftool --probe --verbose'
        pattern = 'Probed: '

        (stdout, stderr, result) = gooftools.run(command, ignore_status=True)

        # Decode successfully matched results
        hwids = [hwid.lstrip(pattern)
                 for hwid in stdout.splitlines()
                 if hwid.startswith(pattern)]

        # Decode unmatched results.
        # Sample output:
        #  Unmatched for /usr/local/share/chromeos-hwid/components_BLAHBLAH:
        #  { 'part_id_3g': ['Actual: XXX', 'Expected: YYY']}
        #  Current System:
        #  { 'part_id_xxx': ['yyy'] },
        str_unmatched = 'Unmatched '
        str_current = 'Current System:'

        start = stderr.find(str_unmatched)
        if start < 0:
            start = 0
        end = stderr.rfind(str_current)
        if end < 0:
            unmatched = stderr[start:]
        else:
            unmatched = stderr[start:end]
        # TODO(hungte) Sort and find best match candidate
        unmatched = '\n'.join([line for line in unmatched.splitlines()
                               # 'gft_hwcomp' or 'probe' are debug message.
                               if not (line.startswith('gft_hwcomp:') or
                                       line.startswith('probe:') or
                                       (not line))])
        # Report the results
        if len(hwids) < 1:
            raise error.TestFail('\n'.join(('No HWID matched.', unmatched)))
        if len(hwids) > 1:
            raise error.TestError('Multiple HWIDs match current system: ' +
                                  ','.join(hwids))
        if result != 0:
            raise error.TestFail('HWID matched (%s) with unknown error: %s'
                                 % hwids[0], result)
        return hwids[0]

    def update_hwid(self, path_to_file):
        """ Updates component list file to shared data LAST_PROBED_HWID_NAME,
            and then let factory_WriteGBB to update system. factory_Finalize
            will verify if that's set correctly.
            This function must not use any GUI resources.

            TODO(hungte) Merge factory_WriteGBB into this test

        Args:
            path_to_component_list: A component list file containing HWID and
            GBB information. Use HWID_AUTODETECT for detection.
        """
        if path_to_file == self.HWID_AUTODETECT:
            path_to_file = self.probe_hwid()
        # Set the factory state sharead data for factory_WriteGBB
        factory.log('Set factory state shared data %s = %s' %
                    (factory.LAST_PROBED_HWID_NAME, path_to_file))
        factory.set_shared_data(factory.LAST_PROBED_HWID_NAME, path_to_file)

    def build_hwid_list(self):
        files = glob.glob('/usr/local/share/chromeos-hwid/components*')
        if not files:
            files = glob.glob('/usr/share/chromeos-hwid/components*')
        files.sort()

        if not files:
            raise error.TestError('No HWID component files found on system.')

        # part_id_hwqual is required for every component list file.
        hwids = [(eval(open(hwid_file).read())['part_id_hwqual'][0], hwid_file)
                 for hwid_file in files ]

        # Add special entries
        special_hwids = [('<Auto Detect>', self.HWID_AUTODETECT)]
        for hwid in hwids:
            if hwid[0] != self.current_hwid:
                continue
            special_hwids += [("<Current Value: %s>" % hwid[0], hwid[1])]
            break

        return special_hwids + hwids

    def key_release_callback(self, widget, event):
        if self.writing:
            return True

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

        char = chr(event.keyval) if event.keyval in range(32,127) else  None
        factory.log('key_release %s(%s)' % (event.keyval, char))
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
        hwid_file = data[1]
        if hwid_file == self.HWID_AUTODETECT:
            self.label.set_text('Probing HWID, Please wait... (may take >30s)')
            self.writing = True
            gtk.main_iteration(False)  # try to update screen
        elif hwid_file:
            factory.log('Selected: %s' % ', '.join(data).replace('\n', ' '))

        try:
            self.update_hwid(hwid_file)
        except Exception, e:
            self._fail_msg = '%s' % e

        gtk.main_quit()
        return True

    def register_callbacks(self, window):
        window.connect('key-release-event', self.key_release_callback)
        window.add_events(gdk.KEY_RELEASE_MASK)

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

    def run_once(self, autodetect=True):
        factory.log('%s run_once' % self.__class__)
        self._fail_msg = None

        if autodetect:
            self.update_hwid(self.HWID_AUTODETECT)
        else:
            # TODO(hungte) add timeout
            self.page_index = 0
            self.pages = 0
            self.writing = False
            with os.popen("crossystem hwid 2>/dev/null", "r") as hwid_proc:
                self.current_hwid = hwid_proc.read()

            self.hwid_list = self.build_hwid_list()
            self.pages = len(self.hwid_list) / self.SELECTION_PER_PAGE
            if len(self.hwid_list) % self.SELECTION_PER_PAGE:
                self.pages += 1

            self.label = ful.make_label('')
            test_widget = gtk.EventBox()
            test_widget.modify_bg(gtk.STATE_NORMAL, ful.BLACK)
            test_widget.add(self.label)
            self.render_page()

            ful.run_test_widget(
                    self.job, test_widget,
                    window_registration_callback=self.register_callbacks)

        factory.log('%s run_once finished' % repr(self.__class__))
        if self._fail_msg:
            raise error.TestFail(self._fail_msg)
