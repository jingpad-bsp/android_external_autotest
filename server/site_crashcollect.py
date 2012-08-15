# Copyright (c) 2011 The Chromium OS Authors. All rights reserved.
# Use of this source code is governed by a BSD-style license that can be
# found in the LICENSE file.

import logging
import os
import urllib2
from autotest_lib.client.common_lib import utils as client_utils
from autotest_lib.client.common_lib.cros import dev_server
from autotest_lib.client.cros import constants
from autotest_lib.server.cros.dynamic_suite.constants import JOB_BUILD_KEY
from autotest_lib.server import utils

def generate_minidump_stacktrace(minidump_path):
    """
    Generates a stacktrace for the specified minidump.

    This function expects the debug symbols to reside under:
        /build/<board>/usr/lib/debug

    @param minidump_path: absolute path to minidump to by symbolicated.
    @raise client_utils.error.CmdError if minidump_stackwalk return code != 0.
    """
    symbol_dir = '%s/../../../lib/debug' % utils.get_server_dir()
    logging.info('symbol_dir: %s' % symbol_dir)
    client_utils.run('minidump_stackwalk %s %s > %s.txt' %
                     (minidump_path, symbol_dir, minidump_path))


def symbolicate_minidump_with_devserver(minidump_path, resultdir):
    """
    Generates a stack trace for the specified minidump by consulting devserver.

    This function assumes the debug symbols have been staged on the devserver.

    @param minidump_path: absolute path to minidump to by symbolicated.
    @param resultdir: server job's result directory.
    @raise DevServerException upon failure, HTTP or otherwise.
    """
    # First, look up what build we tested.  If we can't find this, we can't
    # get the right debug symbols, so we might as well give up right now.
    keyvals = client_utils.read_keyval(resultdir)
    if JOB_BUILD_KEY not in keyvals:
        raise dev_server.DevServerException(
            'Cannot determine build being tested.')

    devserver = dev_server.DevServer.create()
    trace_text = devserver.symbolicate_dump(
        minidump_path, keyvals[JOB_BUILD_KEY])
    if not trace_text:
        raise dev_server.DevServerException('Unknown error!!')
    with open(minidump_path + '.txt', 'w') as trace_file:
        trace_file.write(trace_text)


def find_and_generate_minidump_stacktraces(host_resultdir):
    """
    Finds all minidump files and generates a stack trace for each.

    Enumerates all files under the test results directory (recursively)
    and generates a stack trace file for the minidumps.  Minidump files are
    identified as files with .dmp extension.  The stack trace filename is
    composed by appending the .txt extension to the minidump filename.
    """
    for dir, subdirs, files in os.walk(host_resultdir):
        for file in files:
            if not file.endswith('.dmp'):
                continue
            minidump = os.path.join(dir, file)

            # First, try to symbolicate locally.
            try:
                generate_minidump_stacktrace(minidump)
                logging.info('Generated stack trace for dump %s', minidump)
                continue
            except client_utils.error.CmdError as err:
                logging.warn('Failed to generate stack trace locally for '
                             'dump %s (rc=%d):\n%r',
                             minidump, err.result_obj.exit_status, err)

            # If that did not succeed, try to symbolicate using the dev server.
            try:
                symbolicate_minidump_with_devserver(minidump, host_resultdir)
                logging.info('Generated stack trace for dump %s', minidump)
                continue
            except dev_server.DevServerException as e:
                logging.warn('Failed to generate stack trace on devserver for '
                             'dump %s:\n%r', minidump, e)


def fetch_orphaned_crashdumps(host, host_resultdir):
    for file in host.list_files_glob(os.path.join(constants.CRASH_DIR, '*')):
        logging.info("Collecting %s...", file)
        try:
            host.get_file(file, host_resultdir, preserve_perm=False)
        except Exception as e:
            logging.warning("Collection of %s failed:\n%s", file, e)



def get_site_crashdumps(host, test_start_time):
    host_resultdir = getattr(getattr(host, "job", None), "resultdir", None)
    infodir = os.path.join(host_resultdir, "crashinfo.%s" % host.hostname)
    if not os.path.exists(infodir):
        os.mkdir(infodir)
    fetch_orphaned_crashdumps(host, infodir)
    find_and_generate_minidump_stacktraces(host_resultdir)
