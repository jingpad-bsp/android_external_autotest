#
# Copyright 2008 Google Inc. All Rights Reserved.

"""
The shard module contains the objects and methods used to
manage shards in Autotest.

The valid actions are:
create:      creates shard
remove:      deletes shard(s)
list:        lists shards with label

See topic_common.py for a High Level Design and Algorithm.
"""

import os, sys
from autotest_lib.cli import topic_common, action_common


class shard(topic_common.atest):
    """shard class
    atest shard [create|delete|list] <options>"""
    usage_action = '[create|delete|list]'
    topic = msg_topic = 'shard'
    msg_items = '<shards>'

    def __init__(self):
        """Add to the parser the options common to all the
        shard actions"""
        super(shard, self).__init__()

        self.topic_parse_info = topic_common.item_parse_info(
            attribute_name='shards',
            use_leftover=True)


    def get_items(self):
        return self.shards


class shard_help(shard):
    """Just here to get the atest logic working.
    Usage is set by its parent"""
    pass


class shard_list(action_common.atest_list, shard):
    """Class for running atest shard list [--label <labels>]"""

    def parse(self):
        host_info = topic_common.item_parse_info(attribute_name='labels',
                                                 inline_option='labels')
        return super(shard_list, self).parse([host_info])


    def execute(self):
        return super(shard_list, self).execute(op='get_shards')


    def warn_if_label_assigned_to_multiple_shards(self, results):
        """Prints a warning if one label is assigned to multiple shards.

        This should never happen, but if it does, better be safe.

        @param results: Results as passed to output().
        """
        assigned_labels = set()
        for line in results:
            for label in line['labels']:
                if label in assigned_labels:
                    sys.stderr.write('WARNING: label %s is assigned to '
                                     'multiple shards.\n'
                                     'This will lead to unpredictable behavor '
                                     'in which hosts and jobs will be assigned '
                                     'to which shard.\n')
                assigned_labels.add(label)


    def output(self, results):
        self.warn_if_label_assigned_to_multiple_shards(results)
        super(shard_list, self).output(results, ['hostname', 'labels'])


class shard_create(action_common.atest_create, shard):
    """Class for running atest shard create -l <label> <shard>"""
    def __init__(self):
        super(shard_create, self).__init__()
        self.parser.add_option('-l', '--label',
                               help=('Assign LABEL to the SHARD. All jobs that '
                                     'require this label, will be run on the '
                                     'shard.'),
                               type='string',
                               metavar='LABEL')


    def parse(self):
        (options, leftover) = super(shard_create,
                                    self).parse(req_items='shards')
        if not options.label:
            print 'Must provide a label with -l <label>'
            self.parser.print_help()
            sys.exit(1)
        self.data_item_key = 'hostname'
        self.data['label'] = options.label
        return (options, leftover)


class shard_delete(action_common.atest_delete, shard):
    """Class for running atest shard delete <shards>"""
    def __init__(self):
        super(shard_delete, self).__init__()
        self.parser.add_option('-y', '--yes',
                               help=('Answer all questions with yes.'),
                               action='store_true',
                               metavar='LABEL')


    def parse(self):
        (options, leftover) = super(shard_delete, self).parse()
        self.yes = options.yes
        self.data_item_key = 'hostname'
        return (options, leftover)


    def execute(self, *args, **kwargs):
        if self.yes or self._prompt_confirmation():
            return super(shard_delete, self).execute(*args, **kwargs)
        print 'Aborting.'
        return []


    def _prompt_confirmation(self):
        print 'Please ensure the shard host is powered off.'
        print ('Otherwise DUTs might be used by multiple shards at the same '
               'time, which will lead to serious correctness problems.')
        sys.stdout.write('Continue? [y/N] ')
        read = raw_input().lower()
        if read == 'y':
            return True
        return False
