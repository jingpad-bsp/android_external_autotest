# Copyright 2017 The Chromium OS Authors. All rights reserved.
# Use of this source code is governed by a BSD-style license that can be
# found in the LICENSE file.

import logging
import os
import tempfile
import time
import shutil
from threading import Thread

from autotest_lib.client.bin import test, utils
from autotest_lib.client.common_lib import file_utils
from autotest_lib.client.common_lib import error
from autotest_lib.client.common_lib.cros import chrome
from fake_printer import FakePrinter

_SCRIPT_TIMEOUT = 5
_PRINTER_ADD_TIMEOUT = 3
_FAKE_SERVER_JOIN_TIMEOUT = 10

class platform_AddPrinter(test.test):
    """
    Chrome is brought up, and a cups printer that requires the epson
    driver to be downloaded as a component is configured.  The test verifies
    that the component is downloaded and a subsequent print command works.
    """
    version = 1

    def initialize(self, ppd_file):
        """
        Args:
        @param ppd_file: ppd file name
        """

        # Instantiate Chrome browser.
        with tempfile.NamedTemporaryFile() as cap:
            file_utils.download_file(chrome.CAP_URL, cap.name)
            password = cap.read().rstrip()

        extra_flags = ['--enable-features=CrOSComponent']
        self.browser = chrome.Chrome(gaia_login=False,
                                     username=chrome.CAP_USERNAME,
                                     password=password,
                                     extra_browser_args=extra_flags)
        self.tab = self.browser.browser.tabs[0]

        # Set file path.
        current_dir = os.path.dirname(os.path.realpath(__file__))
        self.pdf_path = os.path.join(current_dir,
                           'to_print.pdf')
        self.printing_log_path = '/tmp/printing_request.log'

        # Download ppd files
        self.ppd_file = '/tmp/%s' % ppd_file
        file_utils.download_file(
            'https://storage.googleapis.com/chromiumos-test-assets-public'
            '/platform_AddPrinter/%s' % ppd_file,
            self.ppd_file);

        # Start fake printer.
        printer = FakePrinter()
        self.server_thread = Thread(target = printer.start,
                               args = (self.printing_log_path, ))
        self.server_thread.start();

    def cleanup(self):
        if hasattr(self, 'browser'):
            self.browser.close()

        # Remove temp files
        os.remove(self.ppd_file)
        os.remove(self.printing_log_path)
        # Remove escpr components (if exists)
        shutil.rmtree('/home/chronos/epson-inkjet-printer-escpr',
                      ignore_errors=True);
        shutil.rmtree('/var/lib/imageloader/', ignore_errors=True);
        mount_folder = '/run/imageloader/epson-inkjet-printer-escpr/'
        if os.path.exists(mount_folder):
            for foldername in os.listdir(mount_folder):
                utils.system_output(
                    'umount ' + mount_folder + foldername)
            shutil.rmtree(mount_folder, ignore_errors=True);

    def add_a_printer(self, ppd_path):
        """
        Add a printer through printer settings on chrome://settings

        Args:
        @param ppd_path: path to ppd file
        """
        logging.info('add printer from ppd:' + ppd_path);

        # Navigate to cups setup UI and wait until fully load.
        self.tab.Navigate("chrome://settings/cupsPrinters")
        self.tab.WaitForDocumentReadyStateToBeInteractiveOrBetter(
            timeout=_SCRIPT_TIMEOUT);

        # call getCupsPrintersList to confirm no printer yet added.
        get_added_printer_query = """
            var printerList;
            cr.sendWithPromise("getCupsPrintersList").then(function(defs) {
                printerList = defs['printerList'];
            });
        """;
        self.tab.EvaluateJavaScript(get_added_printer_query);
        self.tab.WaitForJavaScriptCondition('printerList.length == 0',
                                            timeout=_SCRIPT_TIMEOUT)

        # call addCupsPrinter API with ppd file to trigger download.
        add_cups_printer_query = """
            chrome.send("addCupsPrinter", [{
                printerAddress: "127.0.0.1",
                printerDescription: "",
                printerId: "",
                printerManufacturer: "",
                printerModel: "",
                printerName: "printer",
                printerPPDPath: "%s",
                printerProtocol: "socket",
                printerQueue: "ipp/print",
                printerStatus: ""
            }])
        """ % (ppd_path);
        self.tab.EvaluateJavaScript(add_cups_printer_query);

        # Wait for c++ handler to add printer finish.
        time.sleep(_PRINTER_ADD_TIMEOUT)

        # call getCupsPrintersList to confirm printer added.
        get_added_printer_query="""
            cr.sendWithPromise("getCupsPrintersList").then(function(defs) {
                printerList = defs['printerList'];
            });
        """;
        self.tab.EvaluateJavaScript(get_added_printer_query);
        self.tab.WaitForJavaScriptCondition('printerList.length == 1',
                                            timeout=_SCRIPT_TIMEOUT)
        self.printerList = self.tab.EvaluateJavaScript("printerList");

    def print_a_page(self, golden_file_path):
        """
        Print a page and check print request output

        Args:
        @param golden_file_path: path to printing request golden file.

        @raises: error.TestFail if printing request generated cannot be
        verified.
        """

        # Issue print request.
        utils.system_output(
            'lp -d %s %s' %
            (self.printerList[0].get('printerId'), self.pdf_path)
        );
        self.server_thread.join(_FAKE_SERVER_JOIN_TIMEOUT)

        # Verify print request with a golden file.
        output = utils.system_output(
            'cmp %s %s' % (self.printing_log_path, golden_file_path)
        )
        if output:
            error.TestFail('ERROR: Printing request is not verified!')
        logging.info('cmp output:' + output);

    def run_once(self, golden_file):
        """
        Args:
        @param golden_file: printing request golden file name
        """
        current_dir = os.path.dirname(os.path.realpath(__file__))
        self.add_a_printer(self.ppd_file)
        self.print_a_page(os.path.join(current_dir, golden_file));
