#!/usr/bin/env python

"""
Usage:  ./print_host_labels.py IP.or.hostname.here
"""

import sys
import common
from autotest_lib.server.hosts import factory

host = factory.create_host(sys.argv[1])
labels = host.get_labels()
print '\n\n\nLabels:\n'
print labels
