# Copyright (c) 2013 The Chromium OS Authors. All rights reserved.
# Use of this source code is governed by a BSD-style license that can be
# found in the LICENSE file.

"""A simple script to print the log in a readable format.

Usage:   python tools/print_log.py <log_dir>
Example: python tools/print_log.py tests/log/lumpy
"""


import glob
import json
import os
import sys

sys.path.append(os.getcwd())
from firmware_constants import VLOG


GV_DICT = 'vlog_dict'
GV_LIST = 'gv_list'


def _print_log(log_dir):
    ext = '.log'
    filenames = glob.glob(os.path.join(log_dir, '*', '*' + ext))
    print 'filenames: ', filenames
    for filename in filenames:
        print 'Printing %s ...' % filename
        log_dict = {}
        with open(filename) as log_file:
            log_data = json.load(log_file)
            log_dict[GV_DICT] = {}
            for gv in log_data[GV_DICT]:
                print '  ', gv
                log_dict[GV_DICT][gv] = {}
                for validator, score in sorted(log_data[GV_DICT][gv].items()):
                    print '          %s:  %s' % (validator, str(score))
            gv_list = log_data[GV_LIST]
            log_dict[GV_LIST] = gv_list


if __name__ == '__main__':
    if len(sys.argv) != 2 or not os.path.exists(sys.argv[1]):
        print 'Usage: python tools/%s <log_dir>' % sys.argv[0]
        exit(1)
    log_dir = sys.argv[1]
    _print_log(log_dir)
