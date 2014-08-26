#! /usr/bin/python

# Copyright (c) 2014 The Chromium OS Authors. All rights reserved.
# Use of this source code is governed by a BSD-style license that can be
# found in the LICENSE file.

"""
Add power unit information in a csv file to AFE DB as host attributes.

Usage:
    python add_host_powerunit_info.py --csv mapping_file.csv --server cautotest

Each line in mapping_file.csv consists of
device_hostname, powerunit_hostname, powerunit_outlet, hydra_hostname,
seperated by comma. For example

chromeos-rack2-host1,chromeos-rack2-rpm1,.A1,chromeos-197-hydra1.mtv
chromeos-rack2-host2,chromeos-rack2-rpm1,.A2,chromeos-197-hydra1.mtv
...

Workflow:
    <Generate the csv file>
    python generate_rpm_mapping.py --csv mapping_file.csv --server cautotest

    <Upload mapping information in csv file to AFE>
    python add_host_powerunit_info.py --csv mapping_file.csv

"""
import argparse
import csv
import logging
import os
import sys

import common

from autotest_lib.server.cros.dynamic_suite import frontend_wrappers
from autotest_lib.site_utils.rpm_control_system import utils as rpm_utils



# The host attribute key name for get rpm hostname.
POWERUNIT_KEYS = [rpm_utils.POWERUNIT_HOSTNAME_KEY,
                  rpm_utils.POWERUNIT_OUTLET_KEY,
                  rpm_utils.HYDRA_HOSTNAME_KEY]


def add_powerunit_info_to_host(afe, device, keyvals):
    """Add keyvals to the host's attributes in AFE.

    @param device: the device hostname, e.g. 'chromeos1-rack1-host1'
    @param keyvals: A dictionary where keys are the values in POWERUNIT_KEYS.
                    These are the power unit info about the devcie that we
                    are going to insert to AFE as host attributes.
    """
    if not afe.get_hosts(hostname=device):
        logging.debug('No host named %s', device)
        return

    logging.info('Adding host attribues to %s: %s', device, keyvals)
    for key, val in keyvals.iteritems():
        afe.set_host_attribute(key, val, hostname=device)


def add_from_csv(afe, csv_file):
    """Read power unit information from csv and add to host attributes.

    @param csv_file: A csv file, each line consists of device_hostname,
                     powerunit_hostname powerunit_outlet, hydra_hostname
                     separated by comma.
    """
    with open(csv_file) as f:
        reader = csv.reader(f, delimiter=',')
        for row in reader:
            device = row[0].strip()
            hydra = row[3].strip()
            if not hydra:
                hydra = None
            keyvals = dict(zip(
                    POWERUNIT_KEYS,
                    [row[1].strip(), row[2].strip(), hydra]))
            add_powerunit_info_to_host(afe, device, keyvals)


if __name__ == '__main__':
    logging.basicConfig(level=logging.DEBUG)
    parser = argparse.ArgumentParser(
            description='Add power unit information to host attributes.')
    parser.add_argument('--csv', type=str, dest='csv_file', required=True,
                        help='A path to a csv file, each line consists of '
                             'device_name, powerunit_hostname, '
                             'powerunit_outlet, hydra_hostname, separated '
                             'by comma.')
    parser.add_argument('--server', type=str, dest='server', default=None,
                        help='AFE server that the script will be talking to. '
                             'If not speicified, will default to using the '
                             'server in global_config.ini')
    options = parser.parse_args()
    if not os.path.exists(options.csv_file):
        logging.error('%s is not a valid file.', options.csv_file)
        sys.exit(1)

    afe = frontend_wrappers.RetryingAFE(timeout_min=5, delay_sec=10,
                                        server=options.server)
    logging.info('Connected to %s', afe.server)
    add_from_csv(afe, options.csv_file)
