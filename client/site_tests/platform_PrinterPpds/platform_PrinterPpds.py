# Copyright 2018 The Chromium OS Authors. All rights reserved.
# Use of this source code is governed by a BSD-style license that can be
# found in the LICENSE file.

import dbus
import logging
import os
import subprocess

from autotest_lib.client.bin import test
from autotest_lib.client.common_lib import error
from autotest_lib.client.common_lib import file_utils
from autotest_lib.client.common_lib.cros import dbus_send
from autotest_lib.client.cros import debugd_util

import helpers as tools
import fake_printer
import multithreaded_processor

# Timeout for printing documents in seconds
_FAKE_PRINTER_TIMEOUT = 200

# Prefix for CUPS printer name
_FAKE_PRINTER_ID = 'FakePrinter'

# First port number to use, this test uses consecutive ports numbers,
# different for every PPD file
_FIRST_PORT_NUMBER = 9000

# Values are from platform/system_api/dbus/debugd/dbus-constants.h.
_CUPS_SUCCESS = 0

class platform_PrinterPpds(test.test):
    """
    This test gets a list of PPD files and a list of test documents. It tries
    to add printer using each PPD file and to print all test documents on
    every printer created this way. Becasue the number of PPD files to test can
    be large (more then 3K), PPD files are tested simultaneously in many
    threads.

    """
    version = 1


    def _get_filenames_from_PPD_indexes(self):
        """
        It returns all PPD filenames from SCS server.

        @returns a list of PPD filenames without duplicates

        """
        # extracts PPD filenames from all 20 index files (in parallel)
        outputs = self._processor.run(tools.get_filenames_from_PPD_index, 20)
        # joins obtained lists and performs deduplication
        ppd_files = set()
        for output in outputs:
            ppd_files.update(output)
        return list(ppd_files)


    def _load_component(self, component):
        """
        Download filter component via dbus API

        @param component: name of component

        @raises error.TestFail is component is not loaded.

        """
        logging.info('download component:' + component);
        res = dbus_send.dbus_send(
            'org.chromium.ComponentUpdaterService',
            'org.chromium.ComponentUpdaterService',
            '/org/chromium/ComponentUpdaterService',
            'LoadComponent',
            timeout_seconds=20,
            user='root',
            args=[dbus.String(component)])
        if res.response == '':
            message = 'Component %s could not be loaded.' % component
            raise error.TestFail(message)


    def _delete_component(self, component):
        """
        Delete filter component via dbus API

        @param component: name of component

        """
        logging.info('delete component:' + component);
        dbus_send.dbus_send(
            'org.chromium.ComponentUpdaterService',
            'org.chromium.ComponentUpdaterService',
            '/org/chromium/ComponentUpdaterService',
            'UnloadComponent',
            timeout_seconds=20,
            user='root',
            args=[dbus.String(component)])


    def _calculate_full_path(self, path):
        """
        Converts path given as a parameter to absolute path.

        @param path: a path set in configuration (relative, absolute or None)

        @returns absolute path or None if the input parameter was None

        """
        if path is None or os.path.isabs(path):
            return path
        path_current = os.path.dirname(os.path.realpath(__file__))
        return os.path.join(path_current, path)


    def initialize(
            self, path_docs,
            path_ppds=None, path_digests=None, threads_count=8):
        """
        @param path_docs: path to local directory with documents to print
        @param path_ppds: path to local directory with PPD files to test;
                if None is set then all PPD files from the SCS server are
                downloaded and tested
        @param path_digests: path to local directory with digests files for
                test documents; if None is set then content of printed
                documents is not verified
        @param threads_count: number of threads to use

        """
        # This object is used for running tasks in many threads simultaneously
        self._processor = multithreaded_processor.MultithreadedProcessor(
                threads_count)

        # Unpack archives with all PPD files
        path_archive = self._calculate_full_path('ppds_all.tar.xz')
        path_target_dir = self._calculate_full_path('.')
        subprocess.call(['tar', 'xJf', path_archive, '-C', path_target_dir])
        path_archive = self._calculate_full_path('ppds_100.tar.xz')
        subprocess.call(['tar', 'xJf', path_archive, '-C', path_target_dir])

        # Calculates locations of test documents, PPD files and digests files
        self._location_of_test_docs = self._calculate_full_path(path_docs)
        self._location_of_PPD_files = self._calculate_full_path(path_ppds)
        location_of_digests_files = self._calculate_full_path(path_digests)

        # Reads list of test documents
        self._docs = tools.list_entries_from_directory(
                            path=self._location_of_test_docs,
                            with_suffixes=('.pdf'),
                            nonempty_results=True,
                            include_directories=False)

        # Get list of PPD files ...
        if self._location_of_PPD_files is None:
            # ... from the SCS server
            self._ppds = self._get_filenames_from_PPD_indexes()
        else:
            # ... from the given local directory
            self._ppds = tools.list_entries_from_directory(
                            path=self._location_of_PPD_files,
                            with_suffixes=('.ppd','.ppd.gz'),
                            nonempty_results=True,
                            include_directories=False)

        # Load digests files
        self._digests = dict()
        for doc_name in self._docs:
            if location_of_digests_files is None:
                self._digests[doc_name] = dict()
            else:
                digests_name = doc_name + '.digests'
                path = os.path.join(location_of_digests_files, digests_name)
                self._digests[doc_name] = tools.parse_digests_file(path)

        # Load components required by some printers (Epson and Star)
        self._loaded_components = []
        for component in ('epson-inkjet-printer-escpr', 'star-cups-driver'):
            self._load_component(component)
            self._loaded_components.append(component)


    def cleanup(self):
        """
        Cleanup - unloading all loaded components.

        """
        # Deleted components loaded during initialization
        if hasattr(self, '_loaded_components'):
            for component in self._loaded_components:
                self._delete_component(component)

        # Delete directories with PPD files
        path_ppds = self._calculate_full_path('ppds_100')
        file_utils.rm_dir_if_exists(path_ppds)
        path_ppds = self._calculate_full_path('ppds_all')
        file_utils.rm_dir_if_exists(path_ppds)


    def run_once(self, path_outputs=None):
        """
        This is the main test function. It runs the testing procedure for
        every PPD file. Tests are run simultaneously in many threads.

        @param path_outputs: if it is not None, raw outputs sent
                to printers are dumped here; the directory is overwritten if
                already exists (is deleted and recreated)

        @raises error.TestFail if at least one of the tests failed

        """
        # Set directory for output documents
        self._path_output_directory = path_outputs
        if path_outputs is not None:
            # Delete whole directory if already exists
            file_utils.rm_dir_if_exists(path_outputs)

        # Runs tests for all PPD files (in parallel)
        outputs = self._processor.run(self._thread_test_PPD, len(self._ppds))

        # Analyses tests' outputs, prints a summary report and builds a list
        # of PPD filenames that failed
        failures = []
        for i, output in enumerate(outputs):
            ppd_file = self._ppds[i]
            if output != True:
                failures.append(ppd_file)
            else:
                output = 'OK'
            line = "%s: %s" % (ppd_file, output)
            logging.info(line)

        # Calculate digests files for output documents (if dumped)
        if self._path_output_directory is not None:
            # loads list of outputs to omit
            blacklist = tools.load_blacklist()
            # generates digest file fo each output directory
            for doc_name in self._docs:
                path = os.path.join(self._path_output_directory, doc_name)
                digests = tools.calculate_list_of_digests(path, blacklist)
                with open(path + '.digests', 'wb') as file_digests:
                    file_digests.write(digests)

        # Raises an exception if at least one test failed
        if len(failures) > 0:
            failures.sort()
            raise error.TestFail(
                    'Test failed for %d PPD files: %s'
                    % (len(failures), ', '.join(failures)) )


    def _thread_test_PPD(self, task_id):
        """
        Runs a test procedure for single PPD file.

        It retrieves assigned PPD file and run for it a test procedure.

        @param task_id: an index of the PPD file in self._ppds

        @returns True when the test was passed or description of the error
                (string) if the test failed

        """
        # Gets content of the PPD file
        try:
            ppd_file = self._ppds[task_id]
            if self._location_of_PPD_files is None:
                # Downloads PPD file from the SCS server
                ppd_content = tools.download_PPD_file(ppd_file)
            else:
                # Reads PPD file from local filesystem
                path_ppd = os.path.join(self._location_of_PPD_files, ppd_file)
                with open(path_ppd, 'rb') as ppd_file_descriptor:
                    ppd_content = ppd_file_descriptor.read()
        except BaseException as e:
            return 'MISSING PPD: ' + str(e)

        # Runs the test procedure
        try:
            port = _FIRST_PORT_NUMBER + task_id
            self._PPD_test_procedure(ppd_file, ppd_content, port)
        except BaseException as e:
            return 'FAIL: ' + str(e)

        return True


    def _PPD_test_procedure(self, ppd_name, ppd_content, port):
        """
        Test procedure for single PPD file.

        It tries to run the following steps:
        1. Starts an instance of FakePrinter
        2. Configures CUPS printer
        3. Sends tests documents to the CUPS printer
        4. Fetches the raw document from the FakePrinter
        5. Dumps the raw document if self._path_output_directory is set
        6. Verifies raw document's digest if the digest is available
        7. Removes CUPS printer and stops FakePrinter
        If the test fails this method throws an exception.

        @param ppd_content: a content of the PPD file
        @param port: a port for the printer

        @throws Exception when the test fails

        """
        # Starts the fake printer
        with fake_printer.FakePrinter(port) as printer:

            # Add a CUPS printer manually with given ppd file
            cups_printer_id = _FAKE_PRINTER_ID + '_at_%05d' % port
            result = debugd_util.iface().CupsAddManuallyConfiguredPrinter(
                                         cups_printer_id,
                                         'socket://127.0.0.1:%d' % port,
                                         dbus.ByteArray(ppd_content))
            if result != _CUPS_SUCCESS:
                raise Exception('valid_config - Could not setup valid '
                    'printer %d' % result)

            # Prints all test documents
            try:
                for doc_name in self._docs:
                    # Full path to the test document
                    path_doc = os.path.join(
                                    self._location_of_test_docs, doc_name)
                    # Sends test document to printer
                    subprocess.call(['lp', '-d', cups_printer_id, path_doc])
                    # Gets the output document from the fake printer
                    doc = printer.fetch_document(_FAKE_PRINTER_TIMEOUT)
                    # Dumps output document to the output directory (if set)
                    if self._path_output_directory is not None:
                        path_out_dir = os.path.join(
                                    self._path_output_directory, doc_name)
                        # Creates directory if not exists
                        file_utils.make_leaf_dir(path_out_dir)
                        # Dumps document to a file
                        path_out_file = os.path.join(
                                    path_out_dir, ppd_name + '.out')
                        with open(path_out_file, 'wb') as file_out:
                            file_out.write(doc)
                        # Compresses the file (-n -> do not include timestamp)
                        subprocess.call(['gzip', '-9n', path_out_file])

                    # Check document's digest (if known)
                    if ( ppd_name in self._digests[doc_name] ):
                        digest_expected = self._digests[doc_name][ppd_name]
                        if digest_expected != tools.calculate_digest(doc):
                            message = 'Document\'s digest does not match'
                            raise Exception(message)
                    else:
                        # Simple validation
                        if len(doc) < 16:
                            raise Exception('Empty output')

            finally:
                # remove CUPS printer
                result = debugd_util.iface().CupsRemovePrinter(cups_printer_id)

        # The fake printer is stopped at the end of "with" statement
