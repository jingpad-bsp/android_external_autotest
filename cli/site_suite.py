# Copyright (c) 2012 The Chromium OS Authors. All rights reserved.
# Use of this source code is governed by a BSD-style license that can be
# found in the LICENSE file.

"""
The job module contains the objects and methods used to
manage jobs in Autotest.

The valid actions are:
list:    lists job(s)
create:  create a job
abort:   abort job(s)
stat:    detailed listing of job(s)

The common options are:

See topic_common.py for a High Level Design and Algorithm.
"""

from autotest_lib.cli import topic_common, action_common


class site_suite(topic_common.atest):
    """Suite class
    atest suite [create] [options]"""
    usage_action = '[create]'
    topic = msg_topic = 'suite'
    msg_items = ''


class site_suite_help(site_suite):
    """Just here to get the atest logic working.
    Usage is set by its parent"""
    pass


class site_suite_create(action_common.atest_create, site_suite):
    """Class containing the code for creating a suite."""
    msg_items = 'suite_id'

    def __init__(self):
        super(site_suite_create, self).__init__()

        self.parser.add_option('-b', '--board', help='Board to test. Required.',
                               metavar='BOARD')
        self.parser.add_option('-i', '--build',
                               help='OS image to install before running the '
                                    'test, e.g. '
                                    'x86-alex-release/R17-1412.144.0-a1-b115.'
                                    ' Required.',
                               metavar='BUILD')


    def parse(self):
        board_info = topic_common.item_parse_info(attribute_name='board',
                                                  inline_option='board')
        build_info = topic_common.item_parse_info(attribute_name='build',
                                                  inline_option='build')
        suite_info = topic_common.item_parse_info(attribute_name='name',
                                                  use_leftover=True)

        options, leftover = site_suite.parse(self,
            [suite_info, board_info, build_info], req_items='name')
        self.data = {}
        name = getattr(self, 'name')
        if len(name) > 1:
            self.invalid_syntax('Too many arguments specified, only expected '
                                'to receive suite name: %s' % name)
        self.data['suite_name'] = name[0]
        if options.board:
            self.data['board'] = options.board
        else:
            self.invalid_syntax('--board is required.')
        if options.build:
            self.data['build'] = options.build
        else:
            self.invalid_syntax('--build is required.')

        return options, leftover


    def execute(self):
        return [self.execute_rpc(op='create_suite_job', **self.data)]
