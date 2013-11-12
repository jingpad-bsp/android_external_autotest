# Copyright (c) 2013 The Chromium OS Authors. All rights reserved.
# Use of this source code is governed by a BSD-style license that can be
# found in the LICENSE file.

"""Uploads performance data to the performance dashboard.

Performance tests may output data that needs to be displayed on the performance
dashboard.  The autotest TKO parser invokes this module with each test
associated with a job.  If a test has performance data associated with it, it
is uploaded to the performance dashboard.  The performance dashboard is owned
by Chrome team and is available here: https://chromeperf.appspot.com/.  Users
must be logged in with an @google.com account to view chromeOS perf data there.

"""

import httplib, json, math, os, urllib, urllib2

import common
from autotest_lib.tko import utils as tko_utils

_ROOT_DIR = os.path.dirname(os.path.abspath(__file__))
_PRESENTATION_CONFIG_FILE = os.path.join(
        _ROOT_DIR, 'perf_dashboard_config.json')
_DEFAULT_MASTER_NAME = 'ChromeOSPerf'
_DASHBOARD_UPLOAD_URL = 'https://chromeperf.appspot.com/add_point'


def _aggregate_iterations(perf_values):
    """Aggregate same measurements from multiple iterations.

    Each perf measurement may exist multiple times across multiple iterations
    of a test.  Here, the results for each unique measured perf metric are
    aggregated across multiple iterations.

    @param perf_values: A list of tko.models.perf_value_iteration objects.

    @return A dictionary mapping each unique measured perf value (keyed by
        its description) to information about that perf value (in particular,
        the value is a list of values for each iteration).

    """
    perf_data = {}
    for perf_iteration in perf_values:
        for perf_dict in perf_iteration.perf_measurements:
            if perf_dict['description'] not in perf_data:
                perf_data[perf_dict['description']] = {
                    'units': perf_dict['units'],
                    'higher_is_better': perf_dict['higher_is_better'],
                    'graph': perf_dict['graph'],
                    'value': [perf_dict['value']],   # Note: a list of values.
                    'stddev': perf_dict['stddev']
                }
            else:
                perf_data[perf_dict['description']]['value'].append(
                        perf_dict['value'])
                # Note: the stddev will be recomputed later when the results
                # from each of the multiple iterations are averaged together.
    return perf_data


def _mean_and_stddev(data, precision=4):
    """Computes mean and standard deviation from a list of numbers.

    Assumes that the list contains at least 2 numbers.

    @param data: A list of numeric values.
    @param precision: The integer number of decimal places to which to
        round the results.

    @return A 2-tuple (mean, standard_deviation), in which each value is
        rounded to |precision| decimal places.

    """
    n = len(data)
    mean = float(sum(data)) / n
    # Divide by n-1 to compute "sample standard deviation".
    variance = sum([(elem - mean) ** 2 for elem in data]) / (n - 1)
    return round(mean, precision), round(math.sqrt(variance), precision)


def _compute_avg_stddev(perf_data):
    """Compute average and standard deviations as needed for perf measurements.

    For any perf measurement that exists in multiple iterations (has more than
    one measured value), compute the average and standard deviation for it and
    then store the updated information in the dictionary.

    @param perf_data: A dictionary of measured perf data as computed by
        _aggregate_iterations(), except each value is now a single value, not a
        list of values.

    """
    for perf_dict in perf_data.itervalues():
        if len(perf_dict['value']) > 1:
            perf_dict['value'], perf_dict['stddev'] = (
                    _mean_and_stddev(map(float, perf_dict['value'])))
        else:
            perf_dict['value'] = perf_dict['value'][0]  # Take out of list.


def _parse_config_file():
    """Parses a presentation config file and stores the info into a dict.

    The config file contains information about how to present the perf data
    on the perf dashboard.  This is required if the default presentation
    settings aren't desired for certain tests.

    @return A dictionary mapping each unique autotest name to a dictionary
        of presentation config information.

    """
    json_obj = []
    if os.path.exists(_PRESENTATION_CONFIG_FILE):
        with open(_PRESENTATION_CONFIG_FILE, 'r') as fp:
            json_obj = json.load(fp)
    config_dict = {}
    for entry in json_obj:
        config_dict[entry['autotest_name']] = entry
    return config_dict


def _gather_presentation_info(config_data, test_name):
    """Gathers presentation info from config data for the given test name.

    @param config_data: A dictionary of dashboard presentation info for all
        tests, as returned by _parse_config_file().  Info is keyed by autotest
        name.
    @param test_name: The name of an autotest.

    @return A dictionary containing presentation information extracted from
        |config_data| for the given autotest name.
    """
    master_name = _DEFAULT_MASTER_NAME
    if test_name in config_data:
        presentation_dict = config_data[test_name]
        if 'master_name' in presentation_dict:
            master_name = presentation_dict['master_name']
        if 'dashboard_test_name' in presentation_dict:
            test_name = presentation_dict['dashboard_test_name']
    return {'master_name': master_name, 'test_name': test_name}


def _format_for_upload(platform_name, cros_version, chrome_version, perf_data,
                       presentation_info):
    """Formats perf data suitably to upload to the perf dashboard.

    The perf dashboard expects perf data to be uploaded as a
    specially-formatted JSON string.  In particular, the JSON object must be a
    dictionary with key "data", and value being a list of dictionaries where
    each dictionary contains all the information associated with a single
    measured perf value: master name, bot name, test name, perf value, error
    value, units, and build version numbers.

    @param platform_name: The string name of the platform.
    @param cros_version: The string chromeOS version number.
    @param chrome_version: The string chrome version number.
    @param perf_data: A dictionary of measured perf data as computed by
        _compute_avg_stddev().
    @param presentation_info: A dictionary of dashboard presentation info for
        the given test, as identified by _gather_presentation_info().

    @return A dictionary containing the formatted information ready to upload
        to the performance dashboard.

    """
    dash_entries = []
    for desc in perf_data:
        # Each perf metric is named by a path that encodes the test name,
        # a graph name (if specified), and a description.  This must be defined
        # according to rules set by the Chrome team, as implemented in:
        # chromium/tools/build/scripts/slave/results_dashboard.py.
        data = perf_data[desc]
        if desc.endswith('_ref'):
            desc = 'ref'
        desc = desc.replace('_by_url', '')
        desc = desc.replace('/', '_')
        if data['graph']:
            test_path = '%s/%s/%s' % (presentation_info['test_name'],
                                      data['graph'], desc)
        else:
            test_path = '%s/%s' % (presentation_info['test_name'], desc)

        new_dash_entry = {
            'master': presentation_info['master_name'],
            'bot': 'cros-' + platform_name,  # Prefix to clarify it's chromeOS.
            'test': test_path,
            'value': data['value'],
            'error': data['stddev'],
            'units': data['units'],
            'supplemental_columns': {
                'r_cros_version': cros_version,
                'r_chrome_version': chrome_version,
            }
        }

        dash_entries.append(new_dash_entry)

    json_string = json.dumps(dash_entries)
    return {'data': json_string}


def _send_to_dashboard(data_obj):
    """Sends formatted perf data to the perf dashboard.

    @param data_obj: A formatted data object as returned by
        _format_for_upload().

    @return None, if the data was uploaded without an exception, or a string
        error message if an exception was raised when uploading.

    """
    encoded = urllib.urlencode(data_obj)
    req = urllib2.Request(_DASHBOARD_UPLOAD_URL, encoded)
    try:
        urllib2.urlopen(req)
    except urllib2.HTTPError, e:
        return 'HTTPError: %d for JSON %s\n' % (e.code, data_obj['data'])
    except urllib2.URLError, e:
        return 'URLError: %s for JSON %s\n' % (str(e.reason), data_obj['data'])
    except httplib.HTTPException:
        return 'HTTPException for JSON %s\n' % data_obj['data']


def upload_test(job, test):
    """Uploads any perf data associated with a test to the perf dashboard.

    @param job: An autotest tko.models.job object that is associated with the
        given |test|.
    @param test: An autotest tko.models.test object that may or may not be
        associated with measured perf data.

    """
    if not test.perf_values:
        return

    # Aggregate values from multiple iterations together.
    perf_data = _aggregate_iterations(test.perf_values)

    # Compute averages and standard deviations as needed for measured perf
    # values that exist in multiple iterations.  Ultimately, we only upload a
    # single measurement (with standard deviation) for every unique measured
    # perf metric.
    _compute_avg_stddev(perf_data)

    # Format the perf data for the upload, then upload it.
    test_name = test.testname
    platform_name = job.machine_group
    cros_version = test.attributes.get('CHROMEOS_RELEASE_VERSION', '')
    chrome_version = test.attributes.get('CHROME_VERSION', '')
    # Prefix the chromeOS version number with the chrome milestone.
    # TODO(dennisjeffrey): Modify the dashboard to accept the chromeOS version
    # number *without* the milestone attached.
    cros_version = chrome_version[:chrome_version.find('.') + 1] + cros_version
    config_data = _parse_config_file()
    presentation_info = _gather_presentation_info(config_data, test_name)
    formatted_data = _format_for_upload(
            platform_name, cros_version, chrome_version, perf_data,
            presentation_info)
    error = _send_to_dashboard(formatted_data)

    if error:
        tko_utils.dprint('Error when uploading perf data to the perf '
                         'dashboard for test %s: %s' % (test_name, error))
    else:
        tko_utils.dprint('Successfully uploaded perf data to the perf '
                         'dashboard for test %s.' % test_name)
