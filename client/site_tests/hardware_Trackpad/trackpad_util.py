# Copyright (c) 2011 The Chromium OS Authors. All rights reserved.
# Use of this source code is governed by a BSD-style license that can be
# found in the LICENSE file.

''' Trackpad utility program for reading test configuration data '''

import os


record_program = 'evemu-record'
trackpad_test_conf = 'trackpad_test.conf'
trackpad_device_file_hardcoded = '/dev/input/event6'

# The following global variables are read by execfile the configuration file
gesture_files_path = None
trackpad_device_file = None
area = None
functionality_list = None
filename_attr = None


class TrackpadTestFunctionality:
    ''' Define the attributes of test functionality

    name: functionality name, e.g., any_finger_click
    subname: additional property for the name
            e.g., up or down for two_finger_scroll
    description: description of the functionality
    prompt, subprompt: Prompt messages about a functionality and its subname
            when recording
    area: functionality area. e.g., '1 finger point & click'
    criteria: configurable criteria associated with a particular functionality
    weight: the weight of each functionality, used to calculate how well a
            driver performs
    enabled: True or False to indicate if this functionality is enabled for
            testing
    files: the test files for the functionality
    '''

    def __init__(self, name=None, subname=None, description=None, prompt=None,
                 subprompt=None, area=None, criteria=None, weight=1,
                 enabled=True, files=None):
        self.name = name
        self.subname = subname
        self.description = description
        self.prompt = prompt
        self.subprompt = subprompt
        self.area = area
        self.criteria = criteria
        self.weight = weight
        self.enabled = enabled
        self.files = files


def read_trackpad_test_conf(target_name, path):
    ''' Read target item from the configuration file

    target_name: a target variable to read, e.g., 'functionality_list'
    path: the path of the configuration file

    This function parses the configuration file to derive the target variable.
    Once having parsed the configuration file, this module has obtained all
    configuration variables. This module will keep all such variables in its
    global space. Next time this function is called, a variable can be returned
    immediately without parsing the configuration file again.
    '''
    target = eval(target_name)
    if target is None:
        trackpad_test_conf_path = os.path.join(path, trackpad_test_conf)
        execfile(trackpad_test_conf_path, globals())
        target = eval(target_name)
    return target
