#!/usr/bin/env python
# Copyright (c) 2012 The Chromium OS Authors. All rights reserved.
# Use of this source code is governed by a BSD-style license that can be
# found in the LICENSE file.

"""Script to compare the performance of two different chromeOS builds.

This script is meant to be used when the performance impact of a change in
chromeOS needs to be analyzed. It requires that you have already created two
chromeOS test images (one with the change, and one without), and that you have
at least one device available on which to run performance tests.

This script is actually a light-weight wrapper around crosperf, a tool for
automatically imaging one or more chromeOS devices with particular builds,
running a set of tests on those builds, and then notifying the user of test
results (along with some statistical analysis of perf keyvals). This wrapper
script performs the following tasks:

1) Creates a crosperf "experiment" file to be consumed by crosperf.
2) Invokes crosperf using the created experiment file. Crosperf produces 2
outputs: an e-mail that is sent to the user who invoked it; and an output
folder that is named based on the given --experiment-name, which is created in
the directory in which this script was run.
3) Parses the results of crosperf and outputs a summary of relevant data. This
script produces output in a CSV file, as well as in stdout.

Before running this script for the first time, you should set up your system to
run sudo without prompting for a password (otherwise, crosperf prompts for a
sudo password). You should only have to do that once per host machine.

Once you're set up with passwordless sudo, you can run the script (preferably
from an empty directory, since several output files are produced):

> python perf_compare.py --crosperf=CROSPERF_EXE --image-1=IMAGE_1 \
  --image-2=IMAGE_2 --board=BOARD --remote=REMOTE

You'll need to specify the following inputs: the full path to the crosperf
executable; the absolute paths to 2 locally-built chromeOS images (which must
reside in the "typical location" relative to the chroot, as required by
crosperf); the name of the board associated with the 2 images; and the IP
address of at least one remote device on which to run crosperf. Run with -h to
see the full set of accepted command-line arguments.

Notes:

1) When you run this script, it will delete any previously-created crosperf
output directories and created CSV files based on the specified
--experiment-name.  If you don't want to lose any old crosperf/CSV data, either
move it to another location, or run this script with a different
--experiment-name.
2) This script will only run the benchmarks/perf keys specified in the
file "perf_benchmarks.json".
"""


import json
import logging
import math
import optparse
import os
import re
import shutil
import subprocess
import sys


_ITERATIONS = 5
_IMAGE_1_NAME = 'Image1'
_IMAGE_2_NAME = 'Image2'
_DEFAULT_EXPERIMENT_NAME = 'perf_comparison'
_ROOT_DIR = os.path.dirname(os.path.abspath(__file__))
_BENCHMARK_INFO_FILE_NAME = os.path.join(_ROOT_DIR, 'perf_benchmarks.json')
_CROSPERF_REPORT_LINE_DELIMITER = '\t'
_EXPERIMENT_FILE_NAME = 'experiment.txt'

_BENCHMARK_INFO_TEMPLATE = """
benchmark: {benchmark} {{
  autotest_name: {autotest_name}
  autotest_args: --use_emerged {autotest_args}
  iterations: {iterations}
}}
"""

_IMAGE_INFO_TEMPLATE = """
label: {label} {{
  chromeos_image: {image}
  remote: {remote}
}}
"""


def prompt_for_input(prompt_message):
    """Prompts for user input and returns the inputted text as a string."""
    return raw_input('%s:> ' % prompt_message)


def identify_benchmarks_to_run(benchmark_info, iteration_nums, perf_keys):
    """Identifies which benchmarks to run, and for how many iterations.

    @param benchmark_info: A list of dictionaries containing information about
        the complete set of default perf benchmarks to run.
    @param iteration_nums: See output_benchmarks_info().
    @param perf_keys: See output_benchmarks_info().

    @return A tuple (X, Y), where X is a list of dictionaries containing
        information about the set of benchmarks to run, and Y is the set of
        perf keys requested to be run.
    """
    perf_keys_requested = set()
    benchmarks_to_run = []
    if not perf_keys:
        # Run every benchmark for the specified number of iterations.
        benchmarks_to_run = benchmark_info
        for benchmark in benchmarks_to_run:
            benchmark['iterations'] = iteration_nums[0]
            for perf_key in benchmark['perf_keys']:
                perf_keys_requested.add(perf_key)
    else:
        # Identify which benchmarks to run, and for how many iterations.
        identified_benchmarks = {}
        for i, perf_key in enumerate(perf_keys):
            perf_keys_requested.add(perf_key)
            benchmarks = [benchmark for benchmark in benchmark_info
                          if perf_key in benchmark['perf_keys']]
            if not benchmarks:
                logging.error('Perf key "%s" isn\'t associated with a known '
                              'benchmark.', perf_key)
                sys.exit(1)
            elif len(benchmarks) > 1:
                logging.error('Perf key "%s" is associated with more than one '
                              'benchmark, but should be unique.', perf_key)
                sys.exit(1)
            benchmark_to_add = benchmarks[0]
            benchmark_to_add = identified_benchmarks.setdefault(
                benchmark_to_add['benchmark'], benchmark_to_add)
            if len(iteration_nums) == 1:
                # If only a single iteration number is specified, we assume
                # that applies to every benchmark.
                benchmark_to_add['iterations'] = iteration_nums[0]
            else:
                # The user must have specified a separate iteration number for
                # each perf key.  If the benchmark associated with the current
                # perf key already has an interation number associated with it,
                # choose the maximum of the two.
                iter_num = iteration_nums[i]
                if 'iterations' in benchmark_to_add:
                    benchmark_to_add['iterations'] = (
                        iter_num if iter_num > benchmark_to_add['iterations']
                        else benchmark_to_add['iterations'])
                else:
                    benchmark_to_add['iterations'] = iter_num
        benchmarks_to_run = identified_benchmarks.values()

    return benchmarks_to_run, perf_keys_requested


def output_benchmarks_info(f, iteration_nums, perf_keys):
    """Identifies details of benchmarks to run, and writes that info to a file.

    @param f: A file object that is writeable.
    @param iteration_nums: A list of one or more integers representing the
        number of iterations to run for one or more benchmarks.
    @param perf_keys: A list of one or more string perf keys we need to
        run, or None if we should use the complete set of default perf keys.

    @return Set of perf keys actually requested to be run in the output file.
    """
    benchmark_info = []
    with open(_BENCHMARK_INFO_FILE_NAME, 'r') as f_bench:
        benchmark_info = json.load(f_bench)

    benchmarks_to_run, perf_keys_requested = identify_benchmarks_to_run(
        benchmark_info, iteration_nums, perf_keys)

    for benchmark in benchmarks_to_run:
        f.write(_BENCHMARK_INFO_TEMPLATE.format(
                    benchmark=benchmark['benchmark'],
                    autotest_name=benchmark['autotest_name'],
                    autotest_args=benchmark.get('autotest_args', ''),
                    iterations=benchmark['iterations']))

    return perf_keys_requested


def output_image_info(f, label, image, remote):
    """Writes information about a given image to an output file.

    @param f: A file object that is writeable.
    @param label: A string label for the given image.
    @param image: The string path to the image on disk.
    @param remote: The string IP address on which to install the image.
    """
    f.write(_IMAGE_INFO_TEMPLATE.format(
                label=label, image=image,
                remote=remote.replace(',', ' ')))


def invoke_crosperf(crosperf_exe, result_dir, experiment_name, board, remote,
                    iteration_nums, perf_keys, image_1, image_2, image_1_name,
                    image_2_name):
    """Invokes crosperf with a set of benchmarks and waits for it to complete.

    @param crosperf_exe: The string path to a crosperf executable.
    @param result_dir: The string name of the directory in which crosperf is
        expected to write its output.
    @param experiment_name: A string name to give the crosperf invocation.
    @param board: The string board associated with the locally-built images.
    @param remote: A list of one or more String IP addresses of devices to use
        when invoking crosperf.
    @param iteration_nums: A list of integers representing the number of
        iterations to run for the different benchmarks.
    @param perf_keys: A list of perf keys to run, or None to run the full set
        of default perf benchmarks.
    @param image_1: The string path to the first image.
    @param image_2: The string path to the second image.
    @param image_1_name: A string label to give the first image.
    @param image_2_name: A string label to give the second image.

    @return A tuple (X, Y), where X is the path to the created crosperf report
        file, and Y is the set of perf keys actually requested to be run.
    """
    # Create experiment file for crosperf.
    with open(_EXPERIMENT_FILE_NAME, 'w') as f:
        f.write('name: {name}\nboard: {board}\n'.format(
                    name=experiment_name, board=board))
        perf_keys_requested = output_benchmarks_info(
            f, iteration_nums, perf_keys)
        output_image_info(f, image_1_name, image_1, remote[0])
        output_image_info(f, image_2_name, image_2,
                          remote[1] if len(remote) > 1 else remote[0])

    # Invoke crosperf with the experiment file.
    logging.info('Invoking crosperf with created experiment file...')
    p = subprocess.Popen([crosperf_exe, _EXPERIMENT_FILE_NAME],
                         stdout=subprocess.PIPE, stderr=subprocess.STDOUT)

    # Pass through crosperf output as debug messages until crosperf run is
    # complete.
    while True:
        next_line = p.stdout.readline().strip()
        if not next_line and p.poll() != None:
            break
        logging.debug(next_line)
        sys.stdout.flush()
    p.communicate()
    exit_code = p.returncode

    if exit_code:
        logging.error('Crosperf returned exit code %s', exit_code)
        sys.exit(1)

    report_file = os.path.join(result_dir, 'results.html')
    if not os.path.exists(report_file):
        logging.error('Crosperf report file missing, cannot proceed.')
        sys.exit(1)

    logging.info('Crosperf run complete.')
    logging.info('Crosperf results available in "%s"', result_dir)
    return report_file, perf_keys_requested


def parse_crosperf_report_file(report_file, perf_keys_requested):
    """Reads in and parses a crosperf report file for relevant perf data.

    @param report_file: See generate_results().
    @param perf_keys_requested: See generate_results().

    @return A dictionary containing perf information extracted from the crosperf
        report file.
    """
    results = {}
    with open(report_file, 'r') as f:
        contents = f.read()

        match = re.search(r'summary-tsv.+?/pre', contents, flags=re.DOTALL)
        contents = match.group(0)

        curr_benchmark = None
        for line in contents.splitlines():
            delimiter = r'\s+?'
            match = re.search(
                r'Benchmark:%s(?P<benchmark>\w+?);%sIterations:%s'
                 '(?P<iterations>\w+?)\s' % (delimiter, delimiter, delimiter),
                line)
            if match:
                curr_benchmark = match.group('benchmark')
                iterations = match.group('iterations')
                results[curr_benchmark] = {'iterations': iterations,
                                           'p_values': []}
                continue
            split = line.strip().split(_CROSPERF_REPORT_LINE_DELIMITER)
            if (len(split) == 12 and split[-2] == '--' and
                split[0] not in ['retval', 'iterations'] and
                split[0] in perf_keys_requested):
                results[curr_benchmark]['p_values'].append(
                    (split[0], split[-1]))

    return results


def generate_results(report_file, result_file, perf_keys_requested):
    """Output relevant crosperf results to a CSV file, and to stdout.

    This code parses the "results.html" output file of crosperf. It then creates
    a CSV file that has the following format per line:

    benchmark_name,num_iterations,perf_key,p_value[,perf_key,p_value]

    @param report_file: The string name of the report file created by crosperf.
    @param result_file: A string name for the CSV file to output.
    @param perf_keys_requested: The set of perf keys originally requested to be
        run.
    """
    results = parse_crosperf_report_file(report_file, perf_keys_requested)

    # Output p-value data to a CSV file.
    with open(result_file, 'w') as f:
        for bench in results:
            perf_key_substring = ','.join(
                ['%s,%s' % (x[0], x[1]) for x in results[bench]['p_values']])
            f.write('%s,%s,%s\n' % (
                bench, results[bench]['iterations'], perf_key_substring))

    logging.info('P-value results available in "%s"', result_file)

    # Collect and output some additional summary results to stdout.
    small_p_value = []
    nan_p_value = []
    perf_keys_obtained = set()
    for benchmark in results:
        p_values = results[benchmark]['p_values']
        for key, p_val in p_values:
            perf_keys_obtained.add(key)
            if float(p_val) <= 0.05:
                small_p_value.append((benchmark, key, p_val))
            elif math.isnan(float(p_val)):
                nan_p_value.append((benchmark, key, p_val))

    if small_p_value:
        logging.info('The following perf keys showed statistically significant '
             'result differences (p-value <= 0.05):')
        for item in small_p_value:
            logging.info('* [%s] %s (p-value %s)', item[0], item[1], item[2])
    else:
        logging.info('No perf keys showed statistically significant result '
                     'differences (p-value <= 0.05)')

    if nan_p_value:
        logging.info('The following perf keys had "NaN" p-values:')
        for item in nan_p_value:
            logging.info('* [%s] %s (p-value %s)', item[0], item[1], item[2])

    # Check if any perf keys are missing from what was requested, and notify
    # the user if so.
    for key_requested in perf_keys_requested:
        if key_requested not in perf_keys_obtained:
            logging.warning('Could not find results for requested perf key '
                            '"%s".', key_requested)


def parse_options():
    """Parses command-line arguments."""
    parser = optparse.OptionParser()

    parser.add_option('--crosperf', metavar='PATH', type='string', default=None,
                      help='Absolute path to the crosperf executable '
                           '(required).')
    parser.add_option('--image-1', metavar='PATH', type='string', default=None,
                      help='Absolute path to the first image .bin file '
                           '(required).')
    parser.add_option('--image-2', metavar='PATH', type='string', default=None,
                      help='Absolute path to the second image .bin file '
                           '(required).')
    parser.add_option('--board', metavar='BOARD', type='string', default=None,
                      help='Name of the board associated with the images '
                           '(required).')
    parser.add_option('--remote', metavar='IP[,IP]', type='string',
                      default=None,
                      help='IP address/name of remote device to use; separate '
                           'with a comma if specifying two IP addresses '
                           '(required).')

    parser.add_option('--image-1-name', metavar='NAME', type='string',
                      default=_IMAGE_1_NAME,
                      help='Descriptive name for the first image. Defaults to '
                           '"%default".')
    parser.add_option('--image-2-name', metavar='NAME', type='string',
                      default=_IMAGE_2_NAME,
                      help='Descriptive name for the second image. Defaults to '
                           '"%default".')
    parser.add_option('--experiment-name', metavar='NAME', type='string',
                      default=_DEFAULT_EXPERIMENT_NAME,
                      help='A descriptive name for the performance comparison '
                           'experiment to run. Defaults to "%default".')

    parser.add_option('--perf-keys', metavar='KEY1[,KEY2...]', type='string',
                      default=None,
                      help='Comma-separated list of perf keys to evaluate, '
                           'if you do not want to run the complete set. By '
                           'default, will evaluate with the complete set of '
                           'perf keys.')
    parser.add_option('--iterations', metavar='N1[,N2...]', type='string',
                      default=str(_ITERATIONS),
                      help='Number of iterations to use to evaluate each perf '
                           'key (defaults to %default).  If specifying a '
                           'custom list of perf keys (with --perf-keys) and '
                           'you want to have a different number of iterations '
                           'for each perf key, specify a comma-separated list '
                           'of iteration numbers where N1 corresponds to KEY1, '
                           'N2 corresponds to KEY2, etc.')

    parser.add_option('-v', '--verbose', action='store_true', default=False,
                      help='Use verbose logging.')

    options, _ = parser.parse_args()

    # Verify required command-line parameters have been specified.
    if not options.crosperf:
        parser.error('You must specify the path to a crosperf executable.')
    if not options.image_1 or not options.image_2:
        parser.error('You must specify the paths for 2 image .bin files.')
    if not options.board:
        parser.error('You must specify a board name.')
    if not options.remote:
        parser.error('You must specify at least one remote device to use.')

    return options


def main():
    options = parse_options()

    log_level = logging.DEBUG if options.verbose else logging.INFO
    logging.basicConfig(format='%(asctime)s %(levelname)s: %(message)s',
                        level=log_level)

    # Verify there are no errors in the specified command-line options.
    iteration_nums = [int(i) for i in options.iterations.split(',')]
    perf_keys = options.perf_keys.split(',') if options.perf_keys else None

    if len(iteration_nums) > 1 and not perf_keys:
        logging.error('You should only specify multiple iteration numbers '
                      'if you\'re specifying a custom list of perf keys to '
                      'evaluate.')
        return 1

    if (options.perf_keys and len(iteration_nums) > 1 and
        len(options.perf_keys.split(',')) > len(iteration_nums)):
        logging.error('You specified %d custom perf keys, but only %d '
                      'iteration numbers.', len(options.perf_keys.split(',')),
                      len(iteration_nums))
        return 1

    if not os.path.isfile(options.crosperf):
        logging.error('Could not locate crosperf executable "%s".',
                      options.crosperf)
        if options.crosperf.startswith('/google'):
            logging.error('Did you remember to run prodaccess?')
        return 1

    # Clean up any old results that will be overwritten.
    result_dir = options.experiment_name + '_results'
    if os.path.isdir(result_dir):
        shutil.rmtree(result_dir)
    result_file = options.experiment_name + '_results.csv'
    if os.path.isfile(result_file):
        os.remove(result_file)

    remote = options.remote.split(',')
    report_file, perf_keys_requested = invoke_crosperf(
        options.crosperf, result_dir, options.experiment_name, options.board,
        remote, iteration_nums, perf_keys, options.image_1, options.image_2,
        options.image_1_name, options.image_2_name)
    generate_results(report_file, result_file, perf_keys_requested)

    return 0


if __name__ == '__main__':
    sys.exit(main())