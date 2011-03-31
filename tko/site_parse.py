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
from autotest_lib.client.common_lib import global_config, utils


# Name of the report file to produce upon completion.
_JSON_REPORT_FILE = 'results.json'

# Number of log lines to include with each test.
_LOG_LIMIT = 25


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
        test_name = os.path.basename(test)
        log = os.path.join(test, 'debug', '%s.ERROR' % test_name)

        # If a log doesn't exist, we don't care about this test.
        if not os.path.exists(log):
            continue

        # Pull out only the last _LOG_LIMIT lines of the file.
        short_log = utils.system_output('tail -n %d %s' % (_LOG_LIMIT, log))

        # Let the reader know we've trimmed the log.
        if len(short_log.splitlines()) == _LOG_LIMIT:
            short_log = (
                '[...displaying only the last 25 log lines...]\n' + short_log)

        filtered_results[test_name] = results[test]
        filtered_results[test_name]['log'] = short_log

    # Generate JSON dump of results. Store in results dir.
    json_file = open(os.path.join(results_dir, _JSON_REPORT_FILE), 'w')
    json.dump(filtered_results, json_file)
    json_file.close()


if __name__ == '__main__':
    main()
