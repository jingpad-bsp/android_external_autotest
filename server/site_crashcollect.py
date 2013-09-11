# Copyright (c) 2011 The Chromium OS Authors. All rights reserved.
# Use of this source code is governed by a BSD-style license that can be
# found in the LICENSE file.

import logging
import os
from autotest_lib.client.common_lib import utils as client_utils
from autotest_lib.client.common_lib import error
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
    logging.info('symbol_dir: %s', symbol_dir)
    client_utils.run('minidump_stackwalk "%s" "%s" > "%s.txt"' %
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

    devserver = dev_server.CrashServer.resolve(keyvals[JOB_BUILD_KEY])
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

    @returns The list of generated minidumps.
    """
    minidumps = []
    for dir, subdirs, files in os.walk(host_resultdir):
        for file in files:
            if not file.endswith('.dmp'):
                continue
            minidump = os.path.join(dir, file)

            # First, try to symbolicate locally.
            try:
                generate_minidump_stacktrace(minidump)
                logging.info('Generated stack trace for dump %s', minidump)
                minidumps.append(minidump)
                continue
            except client_utils.error.CmdError as err:
                logging.warn('Failed to generate stack trace locally for '
                             'dump %s (rc=%d):\n%r',
                             minidump, err.result_obj.exit_status, err)

            # If that did not succeed, try to symbolicate using the dev server.
            try:
                minidumps.append(minidump)
                symbolicate_minidump_with_devserver(minidump, host_resultdir)
                logging.info('Generated stack trace for dump %s', minidump)
                continue
            except dev_server.DevServerException as e:
                logging.warn('Failed to generate stack trace on devserver for '
                             'dump %s:\n%r', minidump, e)
    return minidumps


def fetch_orphaned_crashdumps(host, host_resultdir):
    """
    Copy all of the crashes in the crash directory over to the results folder.

    @param host A host object of the device we're to pull crashes from.
    @param host_resultdir The result directory for this host for this test run.
    @return The list of minidumps that we pulled back from the host.
    """
    minidumps = []
    for file in host.list_files_glob(os.path.join(constants.CRASH_DIR, '*')):
        logging.info('Collecting %s...', file)
        host.get_file(file, host_resultdir, preserve_perm=False)
        minidumps.append(file)
    return minidumps


def get_site_crashdumps(host, test_start_time):
    """
    Copy all of the crashdumps from a host to the results directory.

    @param host The host object from which to pull crashes
    @param test_start_time When the test we just ran started.
    @return A list of all the minidumps
    """
    host_resultdir = getattr(getattr(host, 'job', None), 'resultdir', None)
    infodir = os.path.join(host_resultdir, 'crashinfo.%s' % host.hostname)
    if not os.path.exists(infodir):
        os.mkdir(infodir)

    # TODO(milleral): handle orphans differently. crosbug.com/38202
    try:
        orphans = fetch_orphaned_crashdumps(host, infodir)
    except Exception as e:
        orphans = []
        logging.warning('Collection of orphaned crash dumps failed %s', e)

    minidumps = find_and_generate_minidump_stacktraces(host_resultdir)
    orphans.extend(minidumps)

    for minidump in orphans:
        report_bug_from_crash(host, minidump)

    return orphans


def find_packages_of(host, exec_name):
    """
    Find the package that an executable came from.

    @param host A host object that has the executable.
    @param exec_name The name of the executable.
    @return The name of the package that installed the executable.
    """
    packages = []

    # TODO(milleral): It would be significantly faster to iterate through
    # $PATH and run this than to point it at all of /
    find = host.run('find / -executable -type f -name %s' % exec_name)
    for full_path in find.stdout.splitlines():
        # TODO(milleral): This currently shows scary looking error messages
        # in the debug logs via stderr. We only look at stdout, so those
        # get filtered, but it would be good to silence them.
        portageq = host.run('portageq owners / %s' % full_path)
        if portageq.stdout:
            packages.append(portageq.stdout.splitlines()[0].strip())

    # TODO(milleral): This chunk of code is here to verify that mapping
    # executable name to package gives you one and only one package.
    # It is highly questionable as to if this should be left in the
    # production version of this code or not.
    if len(packages) == 0:
        raise error.NoUniquePackageFound('no package for %s' % exec_name)
    if len(packages) > 1:
        # Running through all of /usr/bin in the chroot showed this should
        # never happen, but still maybe possible?
        raise error.NoUniquePackageFound('Crash detection found more than one'
            'package for %s: %s' % exec_name, packages)

    # |len(packages) == 1| at this point, as it should be anyway
    return packages[0]


def report_bug_from_crash(host, minidump_path):
    """
    Given a host to query and a minidump, file a bug about the crash.

    @param host A host object that is where the dump came from
    @param minidump_path The path to the dump file that should be reported.
    """
    # TODO(milleral): Once this has actually been tested, remove the
    # try/except. In the meantime, let's make sure nothing dies because of
    # the fact that this code isn't very heavily tested.
    try:
        meta_path = os.path.splitext(minidump_path)[0] + '.meta'
        with open(meta_path, 'r') as f:
            for line in f.readlines():
                parts = line.split('=')
                if parts[0] == 'exec_name':
                    packages = find_packages_of(host, parts[1].strip())
                    logging.info('Would report crash on %s.', packages)
                    break
    except Exception as e:
        logging.warning('Crash detection failed with: %s', e)
