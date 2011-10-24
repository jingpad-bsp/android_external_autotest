#!/usr/bin/python -u
#
# Copyright (c) 2011 The Chromium OS Authors. All rights reserved.
# Use of this source code is governed by a BSD-style license that can be
# found in the LICENSE file.
#
# Site extension of the default parser. Generate JSON reports and stack traces.
#
# This site parser is used to generate a JSON report of test failures, crashes,
# and the associated logs for later consumption by an Email generator. If any
# crashes are found, the debug symbols for the build are retrieved (either from
# Google Storage or local cache) and core dumps are symbolized.
#
# The parser uses the test report generator which comes bundled with the Chrome
# OS source tree in order to maintain consistency. As well as not having to keep
# track of any secondary failure white lists.
#
# Stack trace generation is done by the minidump_stackwalk utility which is also
# bundled with the Chrome OS source tree. Requires gsutil and cros_sdk utilties
# be present in the path.
#
# The path to the Chrome OS source tree is defined in global_config under the
# CROS section as 'source_tree'.
#
# Existing parse behavior is kept completely intact. If the site parser is not
# configured it will print a debug message and exit after default parser is
# called.
#

import errno, os, json, shutil, sys, tempfile, time

import common
from autotest_lib.client.bin import os_dep, utils
from autotest_lib.client.common_lib import global_config
from autotest_lib.tko import models, parse, utils as tko_utils
from autotest_lib.tko.parsers import version_0


# Name of the report file to produce upon completion.
_JSON_REPORT_FILE = 'results.json'

# Number of log lines to include from error log with each test results.
_ERROR_LOG_LIMIT = 10

# Status information is generally more useful than error log, so provide a lot.
_STATUS_LOG_LIMIT = 50


class StackTrace(object):
    """Handles all stack trace generation related duties. See generate()."""

    # Cache dir relative to chroot.
    _CACHE_DIR = 'tmp/symbol-cache'

    # Flag file indicating symbols have completed processing. One is created in
    # each new symbols directory.
    _COMPLETE_FILE = '.completed'

    # Maximum cache age in days; all older cache entries will be deleted.
    _MAX_CACHE_AGE_DAYS = 1

    # Directory inside of tarball under which the actual symbols are stored.
    _SYMBOL_DIR = 'debug/breakpad'

    # Maximum time to wait for another instance to finish processing symbols.
    _SYMBOL_WAIT_TIMEOUT = 10 * 60

    # Path to JSON test config relative to Autotest root.
    _TEST_CONFIG_PATH = 'utils/dashboard/chromeos_test_config.json'


    def __init__(self, results_dir, cros_src_dir):
        """Initializes class variables.

        Args:
            results_dir: Full path to the results directory to process.
            cros_src_dir: Full path to Chrome OS source tree. Must have a
                working chroot.
        """
        self._results_dir = results_dir
        self._cros_src_dir = cros_src_dir
        self._chroot_dir = os.path.join(self._cros_src_dir, 'chroot')

        # Figure out the location of the test config JSON. Code is modeled after
        # Autotest's standard common.py.
        dirname = os.path.dirname(sys.modules[__name__].__file__)
        autotest_dir = os.path.abspath(os.path.join(dirname, '..'))
        test_config_path = os.path.join(autotest_dir, self._TEST_CONFIG_PATH)

        with open(test_config_path) as f:
            self._test_config = json.load(f)


    def _get_cache_dir(self):
        """Returns a path to the local cache dir, creating if nonexistent.

        Symbol cache is kept inside the chroot so we don't have to mount it into
        chroot for symbol generation each time.

        Returns:
            A path to the local cache dir.
        """
        cache_dir = os.path.join(self._chroot_dir, self._CACHE_DIR)
        if not os.path.exists(cache_dir):
            try:
                os.makedirs(cache_dir)
            except OSError, e:
                if e.errno != errno.EEXIST:
                    raise
        return cache_dir


    def _get_job_name(self):
        """Returns job name read from 'label' keyval in the results dir.

        Returns:
            Job name string.
        """
        return models.job.read_keyval(self._results_dir).get('label')


    def _parse_job_name(self, job_name):
        """Returns a tuple of (board, rev, version) parsed from the job name.

        Handles job names of the form "<board-rev>-<version>...",
        "<board-rev>-<rev>-<version>...", and
        "<board-rev>-<rev>-<version_0>_to_<version>..."

        Args:
            job_name: A job name of the format detailed above.

        Returns:
            A tuple of (board, rev, version) parsed from the job name.
        """
        version = job_name.rsplit('-', 3)[1].split('_')[-1]
        arch, board, rev = job_name.split('-', 3)[:3]
        return '-'.join([arch, board]), rev, version


    def _get_symbol_dir(self, job_name):
        """Returns a path to the symbols dir relative to the chroot.

        Retrieves symbols from Google Storage if they're not available in the
        local cache. Requires gsutil to be present in the path.

        Args:
            job_name: Either a 3-tuple or 4-tuple job name as detailed in
                _parse_job_name.

        Returns:
            A path to the symbols dir relative to the chroot.

        Raises:
            TimeoutError: If unable to acquire processing "lock" for the
                requested symbols. An exception here indicates another instance
                failed unexpectedly.
            ValueError: If the gsutil command is not available.
        """
        cache_dir = self._get_cache_dir()
        board, rev, version = self._parse_job_name(job_name)

        # Symbols are stored under a "<board-rev-version>" folder in the cache.
        symbol_dir = os.path.join(cache_dir, '-'.join([board, rev, version]))

        # We need to return a path relative to the chroot. relpath will strip
        # the leading slash so we need to add it back to ensure the path works
        # inside the chroot.
        symbol_dir_rel_path = os.sep + os.path.relpath(
            symbol_dir, self._chroot_dir)

        # Flag file used to indicate that these symbols have been downloaded and
        # are ready for use.
        symbols_complete_file = os.path.join(symbol_dir, self._COMPLETE_FILE)

        # See if the symbols already exist and have been extracted.
        if os.path.exists(symbols_complete_file):
            # Symbols exist, so return a path relative to the chroot.
            return symbol_dir_rel_path

        # No .completed file available. Maybe another instance is processing
        # the symbols already. Try to make the directory, ensuring either we
        # acquire the "lock" for these symbols or know another instance is
        # handling them in one atomic call.
        try:
            os.mkdir(symbol_dir)
        except OSError as e:
            if e.errno != errno.EEXIST:
                raise

            # Another instance is probably processing these symbols, so wait
            # until timeout for them to complete. Raises a TimeoutError if time
            # elapses and the .completed file is not available.
            utils.poll_for_condition(
                lambda: os.path.exists(symbols_complete_file),
                timeout=self._SYMBOL_WAIT_TIMEOUT, sleep_interval=5,
                desc='Symbols for %s' % '-'.join([board, rev, version]))

            # The other instance finished processing these symbols, so return a
            # path relative to the chroot.
            return symbol_dir_rel_path

        # We've now acquired the 'lock' for these symbols. Now we need to figure
        # out the remote url and start downloading.
        try:
            symbol_file = 'debug-%s.tgz' % board

            # Build Google Storage URL from the test config.
            board_key = '-'.join([board, rev])
            remote_symbol_url = '/'.join([
                self._test_config['boards'][board_key]['archive_server'],
                self._test_config['boards'][board_key]['archive_path'].rsplit(
                    '/', 1)[0] % {'board': board, 'build_version': version},
                symbol_file])

            if not remote_symbol_url.lower().startswith('gs://'):
                raise ValueError(
                    'Invalid symbols URL encountered. Only Google Storage URLs,'
                    ' gs://, are supported.')

            # Use gsutil to copy the file into the cache dir.
            gsutil_cmd = os_dep.command('gsutil')
            utils.run('%s cp %s %s' % (
                gsutil_cmd, remote_symbol_url, symbol_dir))

            # Unpack symbols.
            utils.run('tar zxf %s -C %s %s' % (
                os.path.join(symbol_dir, symbol_file), symbol_dir,
                self._SYMBOL_DIR))

            # No need to keep the tarball around...
            os.remove(os.path.join(symbol_dir, symbol_file))

            # Let any other instances know we've completed processing.
            open(symbols_complete_file, 'w').close()
        except:
            # Something bad happened, remove the symbols directory so another
            # instance can retry.
            shutil.rmtree(symbol_dir)
            raise

        # Return a path relative to the chroot.
        return symbol_dir_rel_path


    def _trim_cache(self):
        """Removes all symbol directories from the cache older than x days.

        Cache age is controlled via _MAX_CACHE_AGE_DAYS constant.
        """
        cache_dir = self._get_cache_dir()

        max_age = time.time() - 60 * 60 * 24 * self._MAX_CACHE_AGE_DAYS
        for symbols in os.listdir(cache_dir):
            symbol_path = os.path.join(cache_dir, symbols)
            if (os.path.isdir(symbol_path)
                    and os.stat(symbol_path).st_mtime < max_age):
                # Multiple callers may be trying to clear the cache at once, so
                # ignore any errors from this call.
                shutil.rmtree(symbol_path, ignore_errors=True)


    def _setup_results_in_chroot(self):
        """Returns a path to the results dir relative to the chroot.

        Uses mount --bind to setup the results directory inside chroot.

        Returns:
            A path to the results dir relative to the chroot.
        """
        # Create temporary directory inside chroot.
        chroot_results_dir = tempfile.mkdtemp(dir=os.path.join(
            self._chroot_dir, 'tmp'))

        utils.run('mkdir -p %s; sudo mount --bind %s %s' % (
            chroot_results_dir, self._results_dir, chroot_results_dir))

        # Return a path relative to the chroot.
        return os.sep + os.path.relpath(chroot_results_dir, self._chroot_dir)


    def _cleanup_results_in_chroot(self, chroot_results_dir):
        """Uses umount to remove mount --bind from inside chroot.

        Args:
            chroot_results_dir: Path to results dir relative to the chroot. Uses
                the path returned by _setup_results_in_chroot().
        """
        # Create directory inside chroot based on results folder name.
        full_chroot_results_dir = os.path.join(
            self._chroot_dir, chroot_results_dir.lstrip(os.sep))

        # unmount results directory from chroot.
        utils.run(
            'sudo umount %s' % full_chroot_results_dir, ignore_status=True)

        # cleanup mount point. Use os.rmdir instead of shutil.rmtree in case the
        # unmount failed. Should only be an empty directory left.
        os.rmdir(full_chroot_results_dir)


    def _generate_stack_traces(self, chroot_symbols_dir, chroot_results_dir):
        """Enters the chroot, finds core dumps, and generate stack traces.

        Args:
            chroot_symbols_dir: Path to symbols dir relative to the chroot.
            chroot_results_dir: Path to results dir relative to the chroot.

        Raises:
            ValueError: If the cros_sdk command is not available.
        """
        # Change to CrOS directory, enter chroot, then find and symbolize dumps.
        cros_sdk_cmd = os_dep.command('cros_sdk')
        utils.run(
            "cd %s; %s -- find %s -name *.dmp -exec "
            "sh -c 'minidump_stackwalk {} %s > {}.txt 2>/dev/null' \;" % (
                self._cros_src_dir, cros_sdk_cmd, chroot_results_dir,
                os.path.join(chroot_symbols_dir, self._SYMBOL_DIR)))


    def generate(self):
        """Main method. Retrieves symbols, manages cache, generate stack traces.

        Given the results directory and Chrome OS source directory provided by
        __init__, generates stack traces for all core dumps in the results dir.

        Stack traces are stored in the same directory as the core dump under the
        name <core dump file>.dmp.txt.
        """
        job_name = self._get_job_name()
        if not job_name:
            tko_utils.dprint(
                'Unable to retrieve label keyval for this job. Stack traces can'
                ' not be generated.')
            return

        # Retrieves symbols from local cache or Google Storage. Path returned is
        # relative to the chroot.
        chroot_symbols_dir = self._get_symbol_dir(job_name)

        # Keep the cache healthy.
        self._trim_cache()

        # Setup links for results dir inside of chroot.
        chroot_results_dir = self._setup_results_in_chroot()

        # Generate stack traces.
        try:
            self._generate_stack_traces(chroot_symbols_dir, chroot_results_dir)
        finally:
            # Cleanup results directory inside of chroot.
            self._cleanup_results_in_chroot(chroot_results_dir)


def parse_reason(path):
    """Process status.log or status and return a test-name: reason dict."""
    status_log = os.path.join(path, 'status.log')
    if not os.path.exists(status_log):
        status_log = os.path.join(path, 'status')
    if not os.path.exists(status_log):
        return

    reasons = {}
    last_test = None
    for line in open(status_log).readlines():
        try:
            # Since we just want the status line parser, it's okay to use the
            # version_0 parser directly; all other parsers extend it.
            status = version_0.status_line.parse_line(line)
        except:
            status = None

        # Assemble multi-line reasons into a single reason.
        if not status and last_test:
            reasons[last_test] += line

        # Skip non-lines, empty lines, and successful tests.
        if not status or not status.reason.strip() or status.status == 'GOOD':
            continue

        # Update last_test name, so we know which reason to append multi-line
        # reasons to.
        last_test = status.testname
        reasons[last_test] = status.reason

    return reasons


def main():
    # Call the original parser.
    parse.main()

    # Results directory should be the last argument passed in.
    results_dir = sys.argv[-1]

    # Load the Chrome OS source tree location.
    cros_src_dir = global_config.global_config.get_config_value(
        'CROS', 'source_tree', default='')

    # We want the standard Autotest parser to keep working even if we haven't
    # been setup properly.
    if not cros_src_dir:
        tko_utils.dprint(
            'Unable to load required components for site parser. Falling back'
            ' to default parser.')
        return

    # Load ResultCollector from the Chrome OS source tree.
    sys.path.append(os.path.join(
        cros_src_dir, 'src/platform/crostestutils/utils_py'))
    from generate_test_report import ResultCollector

    # Collect results using the standard Chrome OS test report generator. Doing
    # so allows us to use the same crash white list and reporting standards the
    # VM based test instances use.
    results = ResultCollector().CollectResults(results_dir)

    # We don't care about successful tests. We only want failed or crashing.
    # Note: .items() generates a copy of the dictionary, so it's safe to delete.
    crashes = False
    for k, v in results.items():
        if v['crashes']:
            crashes = True
        elif v['status'] == 'PASS':
            del results[k]

    # Filter results and collect logs. If we can't find a log for the test, skip
    # it. The Emailer will fill in the blanks using Database data later.
    filtered_results = {}
    for test in results:
        result_log = ''
        test_name = os.path.basename(test)
        error = os.path.join(test, 'debug', '%s.ERROR' % test_name)

        # If the error log doesn't exist, we don't care about this test.
        if not os.path.isfile(error):
            continue

        # Parse failure reason for this test.
        for t, r in parse_reason(test).iteritems():
            # Server tests may have subtests which will each have their own
            # reason, so display the test name for the subtest in that case.
            if t != test_name:
                result_log += '%s: ' % t
            result_log += '%s\n\n' % r.strip()

        # Trim results_log to last _STATUS_LOG_LIMIT lines.
        short_result_log = '\n'.join(
            result_log.splitlines()[-1 * _STATUS_LOG_LIMIT:]).strip()

        # Let the reader know we've trimmed the log.
        if short_result_log != result_log.strip():
            short_result_log = (
                '[...displaying only the last %d status log lines...]\n%s' % (
                    _STATUS_LOG_LIMIT, short_result_log))

        # Pull out only the last _LOG_LIMIT lines of the file.
        short_log = utils.system_output('tail -n %d %s' % (
            _ERROR_LOG_LIMIT, error))

        # Let the reader know we've trimmed the log.
        if len(short_log.splitlines()) == _ERROR_LOG_LIMIT:
            short_log = (
                '[...displaying only the last %d error log lines...]\n%s' % (
                    _ERROR_LOG_LIMIT, short_log))

        filtered_results[test_name] = results[test]
        filtered_results[test_name]['log'] = '%s\n\n%s' % (
            short_result_log, short_log)

    # Generate JSON dump of results. Store in results dir.
    json_file = open(os.path.join(results_dir, _JSON_REPORT_FILE), 'w')
    json.dump(filtered_results, json_file)
    json_file.close()

    # If crashes occurred we need to generate stack traces for the cores.
    if crashes:
        StackTrace(results_dir, cros_src_dir).generate()


if __name__ == '__main__':
    main()
