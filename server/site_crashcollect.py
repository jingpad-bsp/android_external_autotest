# Copyright (c) 2011 The Chromium OS Authors. All rights reserved.
# Use of this source code is governed by a BSD-style license that can be
# found in the LICENSE file.

import logging
import os
from autotest_lib.client.common_lib import utils as client_utils
from autotest_lib.client.cros import constants
from autotest_lib.server import utils

def generate_minidump_stacktrace(minidump_path):
    """
    Generates a stacktrace for the specified minidump.

    This function expects the debug symbols to reside under:
        /build/<board>/usr/lib/debug
    """
    symbol_dir = '%s/../../../lib/debug' % utils.get_server_dir()
    logging.info('symbol_dir: %s' % symbol_dir)
    try:
        result = client_utils.run('minidump_stackwalk %s %s > %s.txt' %
                                  (minidump_path, symbol_dir, minidump_path))
        rc = result.exit_status
    except client_utils.error.CmdError, err:
        rc = err.result_obj.exit_status
    return rc


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
            rc = generate_minidump_stacktrace(minidump)
            if rc == 0:
                logging.info('Generated stack trace for dump %s', minidump)
                return
            else:
                logging.warn('Failed to generate stack trace for ' \
                             'dump %s (rc=%d)' % (minidump, rc))


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
