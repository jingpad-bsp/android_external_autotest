#!/usr/bin/python -u
#
# Copyright (c) 2011 The Chromium OS Authors. All rights reserved.
# Use of this source code is governed by a BSD-style license that can be
# found in the LICENSE file.
#
# Site extension of the default parser. Generates a JSON report of test results.
#
# This site parser is used to generate a JSON report of test failures, crashes,
# and the associated logs for later consumption by an Email generator.
#
# The parser uses the test report generator which comes bundled with the Chrome
# OS source tree in order to maintain consistency. As well as not having to keep
# track of any secondary failure white lists.
#
# The path to the Chrome OS source tree is defined in global_config under the
# CROS section as 'source_tree'.
#
# Existing parse behavior is kept completely intact. If the site parser is not
# configured it will print a debug message and exit after default parser is
# called.
#

import os, json, sys

import common
from autotest_lib.tko import parse, utils as tko_utils
from autotest_lib.tko.parsers import version_0
from autotest_lib.client.common_lib import global_config, utils


# Name of the report file to produce upon completion.
_JSON_REPORT_FILE = 'results.json'

# Number of log lines to include from error log with each test results.
_ERROR_LOG_LIMIT = 10

# Status information is generally more useful than error log, so provide a lot.
_STATUS_LOG_LIMIT = 50


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
    for k, v in results.items():
        if v['status'] == 'PASS' and not v['crashes']:
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


if __name__ == '__main__':
    main()
