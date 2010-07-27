# Copyright (c) 2010 The Chromium OS Authors. All rights reserved.
# Use of this source code is governed by a BSD-style license that can be
# found in the LICENSE file.


# DESCRIPTION :
#
# This library provides common types and routines for the factory ui
# infrastructure.  This library explicitly does not import gtk, to
# allow its use by the autotest control process.


import subprocess
import sys
import time


LOG_PATH = '/var/log/factory.log'
RESULT_FILE_PATH = '/var/run/factory_test_result'


def log(s):
    print >> sys.stderr, 'FACTORY: ' + s


class TestData:
    '''Factory-specific information on the tests to be run.  The label
    and trigger fields contain the description strings to be shown in
    the test control list of the UI.  The trigger field specifies the
    keyboard shortcut to allow on-demain out-of-order test activation.
    The dargs field allows test specific extra arguments.'''

    def __init__(self, label_en='', label_zw='', formal_name=None,
                 tag_prefix=None, trigger=None, automated_seq=[], dargs={},
                 repeat_forever=False):
        self.__dict__.update(vars())

    def __repr__(self):
        d = ['%s=%s' % (l, repr(v))
             for l, v in self.__dict__.items()
             if l != 'self']
        c = ('%s' % self.__class__).rpartition('.')[2]
        return '%s(%s)' % (c, ','.join(d))


def test_map_index(formal_name, tag_prefix):
    return formal_name + '.' + tag_prefix


def make_test_map(test_list):
    return dict((test_map_index(test.formal_name, test.tag_prefix), test)
                for test in test_list)


def make_trigger_set(test_list):
    trigger_map = dict((test.trigger, test) for test in test_list)
    delta = set(test_list) - set(trigger_map.values())
    for test in delta:
        collision = trigger_map[test.trigger]
        log('ERROR: tests %s and %s both have trigger %s' %
            (test.label_en, collision.label_en, test.trigger))
    assert not delta
    return set(trigger_map)


class UiClient:
    '''Support communication with the factory_ui process.  To simplify
    surrounding code, this communication is an exchange of well formed
    python expressions.  Basically send wraps its arguments in a call
    to repr() and recv calls eval() to re-generate the python data.'''

    def __init__(self, factory_ui_path):
        self._proc = subprocess.Popen(factory_ui_path,
                                      stdin=subprocess.PIPE,
                                      stdout=subprocess.PIPE)

    def __del__(self):
        log('control deleting factory_ui subprocess')
        self._proc.terminate()
        time.sleep(1)
        if self._proc.poll() is None:
            self._proc.kill()

    def send(self, x=None):
        print >> self._proc.stdin, repr(x)
        self._proc.stdin.flush()

    def send_cmd_next_test(self):
        self.send(('next_test', None))

    def send_cmd_switch_to(self, trigger):
        self.send(('switch_to', trigger))

    def recv(self):
        return eval(self._proc.stdout.readline().rstrip())

    def recv_target_test_update(self, test_map):
        update = self.recv()
        log('control recv target test %s' % repr(update))
        formal_name, tag_prefix, count = update
        test = test_map.get(test_map_index(formal_name, tag_prefix), None)
        return (test, count)
