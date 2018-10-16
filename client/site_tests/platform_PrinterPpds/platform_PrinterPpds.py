# Copyright 2018 The Chromium OS Authors. All rights reserved.
# Use of this source code is governed by a BSD-style license that can be
# found in the LICENSE file.

import dbus
import logging
import os
import subprocess
import shutil

from autotest_lib.client.bin import test
from autotest_lib.client.common_lib import error
from autotest_lib.client.common_lib import file_utils
from autotest_lib.client.common_lib.cros import dbus_send
from autotest_lib.client.cros import debugd_util

import archiver
import helpers
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
    version = 2


    def _get_filenames_from_PPD_indexes(self):
        """
        It returns all PPD filenames from SCS server.

        @returns a list of PPD filenames without duplicates

        """
        # extracts PPD filenames from all 20 index files (in parallel)
        outputs = self._processor.run(helpers.get_filenames_from_PPD_index, 20)
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
        file_utils.rm_dir_if_exists(os.path.join(path_target_dir,'ppds_all'))
        subprocess.call(['tar', 'xJf', path_archive, '-C', path_target_dir])
        path_archive = self._calculate_full_path('ppds_100.tar.xz')
        file_utils.rm_dir_if_exists(os.path.join(path_target_dir,'ppds_100'))
        subprocess.call(['tar', 'xJf', path_archive, '-C', path_target_dir])

        # Calculates locations of test documents, PPD files and digests files
        self._location_of_test_docs = self._calculate_full_path(path_docs)
        self._location_of_PPD_files = self._calculate_full_path(path_ppds)
        location_of_digests_files = self._calculate_full_path(path_digests)

        # Reads list of test documents
        self._docs = helpers.list_entries_from_directory(
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
            self._ppds = helpers.list_entries_from_directory(
                            path=self._location_of_PPD_files,
                            with_suffixes=('.ppd','.ppd.gz'),
                            nonempty_results=True,
                            include_directories=False)
        self._ppds.sort()

        # Load digests files
        self._digests = dict()
        for doc_name in self._docs:
            if location_of_digests_files is None:
                self._digests[doc_name] = dict()
            else:
                digests_name = doc_name + '.digests'
                path = os.path.join(location_of_digests_files, digests_name)
                self._digests[doc_name] = helpers.parse_digests_file(path)

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
        self._path_output_directory = self._calculate_full_path(path_outputs)
        if self._path_output_directory is not None:
            # Delete whole directory if already exists
            file_utils.rm_dir_if_exists(self._path_output_directory)
            # Create archivers
            self._archivers = dict()
            for doc_name in self._docs:
                path_for_archiver = os.path.join(self._path_output_directory,
                        doc_name)
                self._archivers[doc_name] = archiver.Archiver(path_for_archiver,
                        self._ppds, 50)
            # A place for new digests
            self._new_digests = dict()
            for doc_name in self._docs:
                self._new_digests[doc_name] = dict()

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
            # loads list of ppds to omit
            blacklist = helpers.load_blacklist()
            blacklist += failures
            # generates digest file fo each output directory
            for doc_name in self._docs:
                path = os.path.join(self._path_output_directory,
                        doc_name + '.digests')
                helpers.save_digests_file(path, self._new_digests[doc_name],
                        blacklist)

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
                ppd_content = helpers.download_PPD_file(ppd_file)
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
        # Save the PPD file for an external pipeline
        if self._path_output_directory is not None:
            path_ppd = '/tmp/' + ppd_name
            with open(path_ppd, 'wb') as file_ppd:
                file_ppd.write(ppd_content)
            if path_ppd.endswith('.gz'):
                subprocess.call(['gzip', '-d', path_ppd])
                path_ppd = path_ppd[0:-3]

        try:
            # Starts the fake printer
            with fake_printer.FakePrinter(port) as printer:

                # Add a CUPS printer manually with given ppd file
                cups_printer_id = '%s_at_%05d' % (_FAKE_PRINTER_ID,port)
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
                        job_name = 'job_%05d' % port
                        argv = ['lp', '-d', cups_printer_id, '-t', job_name]
                        argv += [path_doc]
                        subprocess.call(argv)
                        # Gets the output document from the fake printer
                        doc = printer.fetch_document(_FAKE_PRINTER_TIMEOUT)
                        digest = helpers.calculate_digest(doc)
                        # Dumps output document to the output directory (if set)
                        if self._path_output_directory is not None:
                            self._archivers[doc_name].save_file(
                                    ppd_name, '.out', doc, apply_gzip=True)
                            # Set new digest
                            self._new_digests[doc_name][ppd_name] = digest
                            # Reruns the pipeline and dump intermediate outputs
                            path_pipeline = '/tmp/cups_%s' % job_name
                            path_temp_workdir = '/tmp/cups_dir_%s' % job_name
                            if os.path.isfile(path_pipeline):
                                self._rerun_whole_pipeline(path_pipeline,
                                        path_temp_workdir, path_ppd, ppd_name,
                                        path_doc, doc_name, doc)
                        # Check document's digest (if known)
                        if ( ppd_name in self._digests[doc_name] ):
                            digest_expected = self._digests[doc_name][ppd_name]
                            if digest_expected != digest:
                                message = 'Document\'s digest does not match'
                                raise Exception(message)
                        else:
                            # Simple validation
                            if len(doc) < 16:
                                raise Exception('Empty output')

                finally:
                    # remove CUPS printer
                    debugd_util.iface().CupsRemovePrinter(cups_printer_id)

            # The fake printer is stopped at the end of "with" statement
        finally:
            # finalize archivers and cleaning
            if self._path_output_directory is not None:
                for doc_name in self._docs:
                    self._archivers[doc_name].finalize_prefix(ppd_name)
                os.remove(path_ppd)


    def _rerun_whole_pipeline(
            self, path_pipeline, path_temp_workdir, path_ppd, ppd_name,
            path_doc, doc_name, doc):
        """
        Reruns the whole pipeline outside CUPS server.

        Reruns a printing pipeline dumped from CUPS. All intermediate outputs
        are dumped and archived for future analysis.

        @param path_pipeline: a path to file with pipeline dumped from CUPS
        @param path_temp_workdir: a temporary directory to use as working
                directory, it is deleted at the beginning if exists
        @param path_ppd: a path to PPD file
        @param ppd_name: a filenames prefix used for archivers
        @param path_doc: a path to an input (printed) document
        @param doc_name: a document name, used to select a proper archiver
        @param doc: an output produced by CUPS (for comparison)

        """
        shutil.rmtree(path_temp_workdir, ignore_errors=True)
        # edit pipeline script, remove TMPDIR and HOME variables
        with open(path_pipeline, 'rb') as file_pipeline:
            pipeline = file_pipeline.readlines()
        with open(path_pipeline, 'wb') as file_pipeline:
            for line in pipeline:
                if line.startswith('export TMPDIR='):
                    continue
                if line.startswith('export HOME='):
                    continue
                file_pipeline.write(line)
        # create work directory and run pipeline
        os.mkdir(path_temp_workdir)
        path_home_and_tmp_dir = os.path.join(path_temp_workdir,'tmp')
        os.mkdir(path_home_and_tmp_dir)
        my_env = os.environ.copy()
        my_env["TEST_PPD"] = path_ppd
        my_env["TEST_DOCUMENT"] = path_doc
        my_env["HOME"] = my_env["TMPDIR"] = path_home_and_tmp_dir
        argv = ['/bin/bash', '-e', path_pipeline]
        ret = subprocess.Popen(argv, cwd=path_temp_workdir, env=my_env).wait()
        # Archives the script and all intermediate files
        self._archivers[doc_name].move_file(ppd_name, '.sh', path_pipeline)
        i = 0
        while os.path.isfile(os.path.join(path_temp_workdir, "%d.doc" % (i+1))):
            i += 1
            self._archivers[doc_name].copy_file(ppd_name, ".err%d" % i,
                    os.path.join(path_temp_workdir, "%d.err" % i))
            self._archivers[doc_name].copy_file(ppd_name, ".out%d" % i,
                    os.path.join(path_temp_workdir, "%d.doc" % i), True)
        # Reads last output (to compare it with the output produced by CUPS)
        filename_doc = os.path.join(path_temp_workdir, "%d.doc" % i)
        with open(filename_doc, 'rb') as last_file:
            content_digest = helpers.calculate_digest(last_file.read())
        shutil.rmtree(path_temp_workdir, ignore_errors=True)
        # Validation
        if content_digest != helpers.calculate_digest(doc):
            raise Exception("The output returned by the pipeline is different"
                    " than the output produced by CUPS")
        if ret != 0:
            raise Exception("A pipeline script returned %d" % ret)
