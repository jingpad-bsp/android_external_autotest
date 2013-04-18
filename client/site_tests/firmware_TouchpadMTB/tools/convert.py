# Copyright (c) 2013 The Chromium OS Authors. All rights reserved.
# Use of this source code is governed by a BSD-style license that can be
# found in the LICENSE file.

"""A simple script to convert the old log format the its new format.
In the old log format, it only handles tests of single iteration.
In the new log format, it handles tests of multiple iterations.
"""


import glob
import json


GV_DICT = 'vlog_dict'
GV_LIST = 'gv_list'

filenames = glob.glob('tests/logs/*.log')
for filename in filenames:
    print 'Handling %s ...' % filename
    log_dict = {}
    with open(filename) as log_file:
        log_data = json.load(log_file)
        log_dict[GV_DICT] = {}
        for gv in log_data[GV_DICT]:
            print '  ', gv
            log_dict[GV_DICT][gv] = {}
            for validator_score_pair in log_data[GV_DICT][gv]:
                validator = validator_score_pair.keys()[0]
                score = validator_score_pair[validator]
                print '          %s:  %s' % (validator, str(score))
                if log_dict[GV_DICT][gv].get(validator) is None:
                    log_dict[GV_DICT][gv][validator] = []
                log_dict[GV_DICT][gv][validator].append(score)
                score_list = str(log_dict[GV_DICT][gv][validator])
                print '      --> %s: %s' % (validator, score_list)
        gv_list = log_data[GV_LIST]
        log_dict[GV_LIST] = gv_list

    with open(filename + '.new', 'w') as new_log_file:
        json.dump(log_dict, new_log_file)
