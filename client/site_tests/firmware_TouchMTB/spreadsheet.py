# Copyright (c) 2013 The Chromium OS Authors. All rights reserved.
# Use of this source code is governed by a BSD-style license that can be
# found in the LICENSE file.

"""Handle google gdata spreadsheet service."""


import getpass
import glob
import os
import re
import shutil
import subprocess
import sys
import tempfile

import gdata.docs.service
import gdata.spreadsheet
import gdata.spreadsheet.service

import mtb
import test_conf as conf

from common_util import print_and_exit
from firmware_constants import GV


DEFAULT_SPREADSHEET_TITLE = 'Touchpad pressure calibration'

flag_verbose = False


def print_verbose(msg):
    """Print the message if flag_verbose is True.

    @param msg: the message to print
    """
    if flag_verbose:
        print msg


class GestureEventFiles:
    """Get gesture event files and parse the pressure values."""
    DEFAULT_RESULT_DIR = 'latest'
    FILE_PATTERN = '{}.%s*.dat'.format(conf.PRESSURE_CALIBRATION)
    PRESSURE_LIST_MAX_SIZE = 80 * 5

    def __init__(self):
        self._get_machine_ip()
        self._get_result_dir()
        self._get_gesture_event_files()
        self._get_event_pressures()
        self._get_list_of_pressure_dicts()

    def __del__(self):
        self._cleanup()

    def _cleanup(self):
        """Remove the temporary directory that holds the gesture event files."""
        if os.path.isdir(self.event_dir):
            print 'Removing tmp directory "%s" .... ' % self.event_dir
            try:
                shutil.rmtree(self.event_dir)
            except Exception as e:
                msg = 'Error in removing tmp directory ("%s"): %s'
                print_and_exit(msg % (self.event_dir, e))

    def _cleanup_and_exit(self, err_msg):
        """Clean up and exit with the error message.

        @param err_msg: the error message to print
        """
        self._cleanup()
        print_and_exit(err_msg)

    def _get_machine_ip(self):
        """Get the ip address of the chromebook machine."""
        msg = '\nEnter the ip address (xx.xx.xx.xx) of the chromebook machine: '
        self.machine_ip = raw_input(msg)

    def _get_result_dir(self):
        """Get the test result directory located in the chromebook machine."""
        print '\nEnter the test result directory located in the machine.'
        print 'It is a directory under %s' % conf.log_root_dir
        print ('If you have just performed the pressure calibration test '
               'on the machine,\n' 'you could just press ENTER to use '
               'the default "latest" directory.')
        result_dir = raw_input('Enter test result directory: ')
        if result_dir == '':
            result_dir = self.DEFAULT_RESULT_DIR
        self.result_dir = os.path.join(conf.log_root_dir, result_dir)

    def _get_gesture_event_files(self):
        """Scp the gesture event files in the result_dir in machine_ip."""
        try:
            self.event_dir = tempfile.mkdtemp(prefix='touch_firmware_test_')
        except Exception as e:
            err_msg = 'Error in creating tmp directory (%s): %s'
            self._cleanup_and_exit(err_msg % (self.event_dir, e))

        # Try to scp the gesture event files from the chromebook machine to
        # the event_dir created above on the host.
        # An example gesture event file looks like
        #   pressure_calibration.size0-lumpy-fw_11.27-calibration-20130307.dat
        filepath = os.path.join(self.result_dir, self.FILE_PATTERN % '')
        cmd = 'scp root@%s:%s %s' % (self.machine_ip, filepath, self.event_dir)
        try:
            print ('scp gesture event files from "machine_ip:%s" to %s\n' %
                   (self.machine_ip, self.event_dir))
            subprocess.call(cmd.split())
        except subprocess.CalledProcessError as e:
            self._cleanup_and_exit('Error in executing "%s": %s' % (cmd, e))

    def _get_event_pressures(self):
        """Parse the gesture event files to get the pressure values."""
        self.pressures = {}
        self.len_pressures = {}
        for s in GV.SIZE_LIST:
            # Get the gesture event file for every finger size.
            filepath = os.path.join(self.event_dir, self.FILE_PATTERN % s)
            event_files = glob.glob(filepath)
            if not event_files:
                err_msg = 'Error: there is no gesture event file for size %s'
                self._cleanup_and_exit(err_msg % s)

            # Use the latest event file for the size if there are multiple ones.
            event_files.sort()
            event_file = event_files[-1]

            # Get the list of pressures in the event file.
            mtb_packets = mtb.get_mtb_packets_from_file(event_file)
            target_slot = 0
            list_z = mtb_packets.get_slot_data(target_slot, 'pressure')
            len_z = len(list_z)
            if self.PRESSURE_LIST_MAX_SIZE > len_z:
                bgn_index = 0
                end_index = len_z
            else:
                # Get the middle segment of the list of pressures.
                bgn_index = (len_z - self.PRESSURE_LIST_MAX_SIZE) / 2
                end_index = (len_z + self.PRESSURE_LIST_MAX_SIZE) / 2
            self.pressures[s] = list_z[bgn_index : end_index]
            self.len_pressures[s] = len(self.pressures[s])

    def _get_list_of_pressure_dicts(self):
        """Get a list of pressure dictionaries."""
        self.list_of_pressure_dicts = []
        for index in range(max(self.len_pressures.values())):
            pressure_dict = {}
            for s in GV.SIZE_LIST:
                if index < self.len_pressures[s]:
                    pressure_dict[s] = str(self.pressures[s][index])
            self.list_of_pressure_dicts.append(pressure_dict)
            print_verbose('      row %4d: %s' % (index, str(pressure_dict)))


class PressureSpreadsheet(object):
    """A spreadsheet class to perform pressures calibration in worksheets."""
    WORKSHEET_ROW_COUNT = 1000
    WORKSHEET_COL_COUNT = 20
    HEADER_ROW_NUMBER = 1

    def __init__(self, spreadsheet_title, worksheet_title):
        """Initialize the spreadsheet and the worksheet

        @param spreadsheet_title: the spreadsheet title
        @param worksheet_title: the worksheet title
        """
        self._login()
        self._get_spreadsheet_key_by_title(spreadsheet_title)
        self._get_worksheet_id_by_title(worksheet_title)

    def _login(self):
        site = '@chromium.org'
        self.email = raw_input('\nEnter your email address %s: ' % site) + site
        self.password = getpass.getpass('Password of %s: ' % self.email)

        # Set up the spreadsheet client and do ProgrammaticLogin
        self.ss_client = gdata.spreadsheet.service.SpreadsheetsService()
        self.ss_client.email = self.email
        self.ss_client.password = self.password
        self.ss_client.source = 'Touchpad Pressure Calibration'
        try:
            self.ss_client.ProgrammaticLogin()
        except Exception as e:
            print_and_exit('Error: Login failed: %s' % e)

    def _get_spreadsheet_key_by_title(self, spreadsheet_title):
        """Get the list of documents.

        @param spreadsheet_title: the spreadsheet title

        the html of a document looks like:
        "https://docs.google.com/a/chromium.org/spreadsheet/
               ccc?key=0ArmN1oagwBHXdC05V2VMQVJYNHZ6aEVqVDNIZTZqcHc"
        """
        doc_client = gdata.docs.service.DocsService()
        doc_client.ClientLogin(self.email, self.password)
        documents_feed = doc_client.GetDocumentListFeed()
        for doc in documents_feed.entry:
            if (doc.GetDocumentType() == 'spreadsheet' and
                    doc.title.text == spreadsheet_title):
                doc_html = doc.GetHtmlLink().href
                result = re.search('https://.+key=(\w+).*', doc_html)
                if result is None:
                    continue
                self.spreadsheet_key = result.group(1)
                print 'spreadsheet title: ', doc.title.text
                print 'spreadsheet key: ', self.spreadsheet_key
                return self.spreadsheet_key
        print 'Error: cannot find the spreadsheet "%s".' % spreadsheet_title

    def _worksheet_title_exists(self, worksheet_title):
        """Check if the worksheet title exists?"""
        ws_feed = self.ss_client.GetWorksheetsFeed(key=self.spreadsheet_key)
        for i, entry in enumerate(ws_feed.entry):
            if entry.title.text == worksheet_title:
                return True
        return False

    def _get_worksheet_id_by_title(self, worksheet_title,
                                   row_count=WORKSHEET_ROW_COUNT,
                                   col_count=WORKSHEET_COL_COUNT):
        """Create a new worksheet using the title.

        If the worksheet title already exists, using a new title name such as
        "Copy n of title", where n = 2, 3, ..., MAX_TITLE_DUP + 1

        @param title: the worksheet title
        @param row_count: the number of rows in the worksheet
        @param col_count: the number of columns in the worksheet

        An entry id looks like
            https://spreadsheets.google.com/feeds/worksheets/
                  0ArmN1oagwBHXdC05V2VMQVJYNHZ6aEVqVDNIZTZqcHc/private/full/ocp
        """
        MAX_TITLE_DUP = 10
        new_worksheet_title = worksheet_title
        for i in range(2, MAX_TITLE_DUP + 2):
            if not self._worksheet_title_exists(new_worksheet_title):
                break
            new_worksheet_title = 'Copy %d of %s' % (i, worksheet_title)
        else:
            msg = 'Too many duplicate copies of the worksheet title: %s.'
            print_and_exit(msg % worksheet_title)

        # Add the new worksheet and get the worksheet_id.
        self.ws_client = self.ss_client.AddWorksheet(
                new_worksheet_title, row_count, col_count, self.spreadsheet_key)
        self.worksheet_id = self.ws_client.id.text.split('/')[-1]
        print 'worksheet created:', new_worksheet_title
        print 'worksheet id: ', self.worksheet_id

    def _set_column_headers(self):
        """Set column headers for finger sizes in a worksheet."""
        bgn_column = 2
        end_column = 8
        for col in range(bgn_column, end_column + 1):
            col_header = GV.SIZE_LIST[col - bgn_column]
            # print self.HEADER_ROW_NUMBER, col, col_header, self.worksheet_id
            entry = self.ss_client.UpdateCell(self.HEADER_ROW_NUMBER,
                                              col,
                                              col_header,
                                              self.spreadsheet_key,
                                              self.worksheet_id)

    def insert_pressures_to_worksheet(self, list_of_pressure_dicts):
        """Insert the lists of pressures of all finger sizes to a new worksheet.

        @param list_of_pressure_dicts: a list of pressure dictionaries
        """
        # Set column headers for figner sizes
        self._set_column_headers()

        # Insert the pressures row by row
        for pressure_dict in list_of_pressure_dicts:
            print_verbose('      %s' % str(pressure_dict))
            entry = self.ss_client.InsertRow(pressure_dict,
                                             self.spreadsheet_key,
                                             self.worksheet_id)


def get_spreadsheet_title():
    """Get the spreadsheet title."""
    print '\nInput the name of the spreadsheet below. '
    print ('Or press ENTER to use the default spreadsheet "%s".' %
           DEFAULT_SPREADSHEET_TITLE)
    spreadsheet_title = raw_input('Input the spreadsheet name: ')

    if not spreadsheet_title:
        spreadsheet_title = DEFAULT_SPREADSHEET_TITLE
    print 'spreadsheet: ', spreadsheet_title

    return spreadsheet_title


def get_worksheet_title():
    """Get the worksheet title."""
    worksheet_title = ''
    while not worksheet_title:
        print '\nInput the name of the new worksheet to insert the events.'
        print ('This is usually the board name with the firmware version, '
               'e.g., Lumpy 11.27')
        worksheet_title = raw_input('Input the new worksheet name: ')
    return worksheet_title


def main():
    """Parse the gesture events and insert them to the spreadsheet."""
    # Get the gesture event files and parse the events.
    list_of_pressure_dicts = GestureEventFiles().list_of_pressure_dicts

    # Access the spreadsheet, and create a new worksheet to insert the events.
    spreadsheet_title = get_spreadsheet_title()
    worksheet_title = get_worksheet_title()
    ss = PressureSpreadsheet(spreadsheet_title, worksheet_title)
    ss.insert_pressures_to_worksheet(list_of_pressure_dicts)


if __name__ == '__main__':
    argc = len(sys.argv)
    if argc == 2 and sys.argv[1] == '-v':
        flag_verbose = True
    elif argc > 2 or argc == 2:
        print_and_exit('Usage: %s [-v]' % sys.argv[0])

    main()
