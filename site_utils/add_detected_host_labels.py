#!/usr/bin/python

# Copyright (c) 2013 The Chromium OS Authors. All rights reserved.
# Use of this source code is governed by a BSD-style license that can be
# found in the LICENSE file.
"""A small wrapper script, iterates through
the known hosts and tries to call get_labels()
to discover host functionality, and adds these
detected labels to host.

Limitations:
 - Does not keep a count of how many labels were
   actually added.
 - If a label is added by this script because it
   is detected as supported by get_labels, but later becomes
   unsupported, this script has no way to know that it
   should be removed, so it will remain attached to the host.
   See crosbug.com/38569
"""


import logging
import socket
import argparse
import sys

import common

from autotest_lib.server import hosts
from autotest_lib.server import frontend
from autotest_lib.client.common_lib import error


def add_missing_labels(hostname, afe):
    """
    Queries the detectable labels supported by the given host,
    and adds those labels to the host.

    @param hostname: The host to query and update.
    @param afe: A frontend.AFE() instance.

    @return: True on success.
             False on failure to fetch labels or to add any individual label.
    """

    try:
        host = hosts.create_host(hostname)
        labels = host.get_labels()
    except socket.gaierror:
        logging.warning('Unable to establish ssh connection to hostname '
                        '%s. Skipping.', hostname)
        return False
    except error.AutoservError:
        logging.warning('Unable to query labels on hostname %s. Skipping.',
                         hostname)
        return False

    success = True


    for label_name in labels:
        label_matches = afe.get_labels(name=label_name)

        if not label_matches:
            success = False
            logging.warning('Unable to add label %s to host %s. '
                            'Skipping unknown label.', label_name,
                            hostname)
            continue

        label_matches[0].add_hosts(hosts=[hostname])

    return success


def main():
    """"
    Entry point for add_detected_host_labels script.
    """

    parser = argparse.ArgumentParser()
    parser.add_argument('-s', '--silent', dest='silent', action='store_true',
                      help='Suppress logging messages below.')
    parser.add_argument('-i', '--info', dest='info_only', action='store_true',
                      help='Suppress logging messages below INFO priority.')
    options = parser.parse_args()

    if options.silent and options.info_only:
        print 'The -i and -s flags cannot be used together.'
        parser.print_help()
        return 0


    if options.silent:
        logging.disable(logging.CRITICAL)

    if options.info_only:
        logging.disable(logging.DEBUG)

    afe = frontend.AFE()
    labels = afe.get_labels()

    hostnames = afe.get_hostnames()
    failures = 0
    attempts = 0
    for hostname in hostnames:
        if not add_missing_labels(hostname, afe):
            failures += 1

    attempts = len(hostnames)

    logging.info('Label updating finished. Failed update on %d out of %d '
                 'hosts.', failures, attempts)

    return 0


if __name__ == '__main__':
    sys.exit(main())
