# Copyright (c) 2014 The Chromium Authors. All rights reserved.
# Use of this source code is governed by a BSD-style license that can be
# found in the LICENSE file.

import argparse
import copy
import csv
import logging
import os
import re
import shutil

CONNECT_FAIL = object()
CONFIG_FAIL = object()
RESULTS_DIR = '/tmp/chaos'


class ChaosParser(object):
    """Defines a parser for chaos test results"""

    def __init__(self, results_dir):
        """ Constructs a parser interface.

        @param results_dir: complete path to restuls directory for a chaos test.

        """
        self.test_results_dir = results_dir


    def convert_set_to_string(self, set_list):
        """Converts a set to a single string.

        @param set_list: a set to convert

        @returns a string, which is all items separated by the word 'and'

        """
        return_string = str()
        for i in set_list:
            return_string += str('%s and ' % i)
        return return_string[:-5]


    def create_csv(self, filename, data_list):
        """Creates a file in .csv format.

        @param filename: name for the csv file
        @param data_list: a list of all the info to write to a file

        """
        if not os.path.exists(RESULTS_DIR):
            os.mkdir(RESULTS_DIR)
        try:
            path = os.path.join(RESULTS_DIR, filename + '.csv')
            with open(path, 'wb') as f:
                writer = csv.writer(f)
                writer.writerow(data_list)
                logging.info('Created CSV file %s', path)
        except IOError as e:
            logging.error('File operation failed with %s: %s', e.errno,
                           e.strerror)
            return


    def get_ap_name(self, line):
        """Gets the router name from the string passed.

        @param line: Test ERROR string from chaos status.log

        @returns the router name or brand.

        """
        router_info = re.search('Router name: ([\w\s]+)', line)
        return router_info.group(1)


    def get_ap_mode_chan_freq(self, ssid):
        """Gets the AP band from ssid using channel.

        @param ssid: A valid chaos test SSID as a string

        @returns the AP band, mode, and channel.

        """
        channel_security_info = ssid.split('_')
        channel_info = channel_security_info[-2]
        mode = channel_security_info[-3]
        channel = int(re.split('(\d+)', channel_info)[1])
        # TODO Choose if we want to keep band, we never put it in the
        # spreadsheet and is currently unused.
        if channel in range(1, 15):
            band = '2.4GHz'
        else:
            band = '5GHz'
        return {'mode': mode.upper(), 'channel': channel,
                'band': band}


    def generate_percentage_string(self, passed_tests, total_tests):
        """Creates a pass percentage string in the formation x/y (zz%)

        @param passed_tests: int of passed tests
        @param total_tests: int of total tests

        @returns a formatted string as described above.

        """
        percent = float(passed_tests)/float(total_tests) * 100
        percent_string = str(int(round(percent))) + '%'
        return str('%d/%d (%s)' % (passed_tests, total_tests, percent_string))


    def parse_keyval(self, filepath):
        """Parses the 'keyvalue' file to get device details.

        @param filepath: the complete path to the keyval file

        @returns a board with device name and OS version.

        """
        f = open(filepath, 'r')
        for line in f:
            line = line.split('=')
            if 'RELEASE_BOARD' in line[0]:
                lsb_dict = {'board':line[1].rstrip()}
            elif 'RELEASE_VERSION' in line[0]:
                lsb_dict['version'] = line[1].rstrip()
            else:
                continue
        f.close()
        return lsb_dict


    def parse_status_log(self, board, os_version, security, status_log_path):
        """Parses the entire status.log file from chaos test for test failures.
           and creates two CSV files for connect fail and configuration fail
           respectively.

        @param board: the board the test was run against as a string
        @param os_version: the version of ChromeOS as a string
        @param security: the security used during the test as a string
        @param status_log_path: complete path to the status.log file

        """
        # Items that can have multiple values
        modes = list()
        channels = list()
        ap_names = list()
        hostnames = list()
        config_failure = connect_failure = False
        f = open(status_log_path, 'r')
        total = 0
        for line in f:
            line = line.strip()
            if line.startswith('START\tnetwork_WiFi'):
               # TODO: @bmahadev, Add exception for PDU failure and do not
               # include that in the total tests.
               total += 1
            elif 'END ERROR' in line or 'END FAIL' in line:
                if failure_type == CONNECT_FAIL:
                    connect_failure = True
                else:
                    config_failure = True
                failure_type = None
            elif line.startswith('ERROR') or line.startswith('FAIL'):
                if 'Router name' in line:
                    # TODO: Should not appearing in the scan be a connect
                    # failure?
                    ap_names.append(self.get_ap_name(line))
                title_info = line.split()
                # Get the hostname for the AP that failed configuration.
                if 'chromeos' in title_info[1]:
                    failure_type = CONFIG_FAIL
                    hostname = title_info[1].split('.')[1].split('_')[0]
                else:
                    # Get the router name, band for the AP that failed
                    # connect.
                    ssid_info = title_info[1].split('.')
                    ssid = ssid_info[1]
                    if 'ch' not in ssid:
                        ssid = ssid_info[2]

                    network_dict = self.get_ap_mode_chan_freq(ssid)
                    modes.append(network_dict['mode'])
                    channels.append(network_dict['channel'])

                    # Security mismatches and Ping failures are not connect
                    # failures.
                    if ('Ping command' in line or
                        'correct security' in line):
                        failure_type = CONFIG_FAIL
                        hostnames.append(ssid)
                    else:
                        failure_type = CONNECT_FAIL
            elif line.startswith('Debug info'):
                ap_names.append(self.get_ap_name(line))
            else:
                continue

        config_pass = total - len(hostnames)
        config_pass_string = self.generate_percentage_string(len(hostnames),
                                                             total)
        connect_pass_string = self.generate_percentage_string(len(ap_names),
                                                              config_pass)

        # Two blank entries for firmware and kernel versions
        base_csv_list = [board, os_version, "", "",
                         self.convert_set_to_string(set(modes)),
                         self.convert_set_to_string(set(channels)),
                         security]

        connect_csv_list = copy.deepcopy(base_csv_list)
        connect_csv_list.append(connect_pass_string)
        connect_csv_list.extend(ap_names)

        config_csv_list = copy.deepcopy(base_csv_list)
        config_csv_list.append(config_pass_string)
        config_csv_list.extend(hostnames)

        self.create_csv('chaos_WiFi_connect_fail.' + security,
                        connect_csv_list)
        self.create_csv('chaos_WiFi_config_fail.' + security,
                        config_csv_list)


    def traverse_results_dir(self, path):
        """Walks through the results directory and get the pathnames for the
           status.log and the keyval files.

        @param path: complete path to a specific test result directory.

        @returns a dict with absolute pathnames for the 'status.log' and
                'keyfile' files.

        """
        status = None
        keyval = None

        for root, dir_name, file_name in os.walk(path):
            for name in file_name:
                if name == 'status.log':
                    path = os.path.join(root, name)
                    if not status:
                       status = path
                elif name == 'keyval' and 'CHROMEOS_BUILD' in open(os.path.join(
                                                            root, name)).read():
                    path = os.path.join(root, name)
                    keyval = path
                    break
                else:
                    continue
        return {'status_file': status, 'keyval_file': keyval}


    def parse_results_dir(self):
        """Parses each result directory.

        For each results directory created by test_that, parse it and
        create summary files.

        """
        if os.path.exists(RESULTS_DIR):
            shutil.rmtree(RESULTS_DIR)
        test_processed = False
        for results_dir in os.listdir(self.test_results_dir):
            if 'results' in results_dir:
                path = os.path.join(self.test_results_dir, results_dir)
                test = results_dir.split('.')[1]
                status_key_dict = self.traverse_results_dir(path)
                status_log_path = status_key_dict['status_file']
                lsb_info = self.parse_keyval(status_key_dict['keyval_file'])
                if test is not None:
                    self.parse_status_log(lsb_info['board'],
                                          lsb_info['version'],
                                          test,
                                          status_log_path)
                    test_processed = True
        if not test_processed:
            raise RuntimeError('chaos_parse: Did not find any results directory'
                               'to process')


def main():
    """Main function to call the parser."""
    logging.basicConfig(level=logging.INFO)
    arg_parser = argparse.ArgumentParser()
    arg_parser.add_argument('-d', '--directory', dest='dir_name',
                            help='Pathname to results generated by test_that')
    arguments = arg_parser.parse_args()
    if not arguments.dir_name:
        raise RuntimeError('chaos_parser: No directory name supplied. Use -h'
                           ' for help')
    if not os.path.exists(arguments.dir_name):
        raise RuntimeError('chaos_parser: Invalid directory name supplied.')
    parser = ChaosParser(arguments.dir_name)
    parser.parse_results_dir()


if __name__ == '__main__':
    main()
