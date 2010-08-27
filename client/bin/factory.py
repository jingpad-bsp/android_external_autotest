# Copyright (c) 2010 The Chromium OS Authors. All rights reserved.
# Use of this source code is governed by a BSD-style license that can be
# found in the LICENSE file.


# DESCRIPTION :
#
# This library provides common types and routines for the factory ui
# infrastructure.  This library explicitly does not import gtk, to
# allow its use by the autotest control process.


import gobject
import signal
import subprocess
import sys
import time


ACTIVE = 'ACTIVE'
PASSED = 'PASS'
FAILED = 'FAIL'
UNTESTED = 'UNTESTED'

STATUS_CODE_MAP = {
    'START': ACTIVE,
    'GOOD': PASSED,
    'FAIL': FAILED,
    'ERROR': FAILED}


LOG_PATH = '/var/log/factory.log'
DATA_PREFIX = 'FACTORY_DATA:'
FINAL_VERIFICATION_TEST_UNIQUE_NAME = 'factory_Verify'

def log(s):
    print >> sys.stderr, 'FACTORY: ' + s

def log_shared_data(key, value):
    print >> sys.stderr, '%s %s=%s' % (DATA_PREFIX, key, repr(value))

def lookup_status_by_unique_name(unique_name, test_list, status_file_path):
    """ quick way to determine the status of given test """
    status_map = StatusMap(test_list, status_file_path)
    testdb = status_map.test_db
    xtest = testdb.get_test_by_unique_name(unique_name)
    return status_map.lookup_status(xtest)

class FactoryTest:
    def __repr__(self):
        d = ['%s=%s' % (l, repr(v))
             for l, v in self.__dict__.items()
             if l != 'self']
        c = ('%s' % self.__class__).rpartition('.')[2]
        return '%s(%s)' % (c, ','.join(d))

class FactoryAutotestTest(FactoryTest):
    # Placeholder parent for tests with autotest_name fields.
    pass

class OperatorTest(FactoryAutotestTest):
    def __init__(self, label_en='', label_zw='', autotest_name=None,
                 kbd_shortcut=None, dargs={}, drop_caches=False,
                 unique_name=None):
        self.__dict__.update(vars())

class InformationScreen(OperatorTest):
    # These tests never pass or fail, just return to untested state.
    pass

class AutomatedSequence(FactoryTest):
    def __init__(self, label_en='', label_zw='', subtest_tag_prefix=None,
                 kbd_shortcut=None, subtest_list=[], unique_name=None):
        self.__dict__.update(vars())

class AutomatedSubTest(FactoryAutotestTest):
    def __init__(self, label_en='', label_zw='', autotest_name=None,
                 dargs={}, drop_caches=False, unique_name=None):
        self.__dict__.update(vars())

class AutomatedRebootSubTest(FactoryAutotestTest):
    def __init__(self, label_en='', label_zw='', iterations=None,
                 autotest_name='factory_RebootStub', dargs={},
                 drop_caches=False, unique_name=None):
        self.__dict__.update(vars())


class TestDatabase:

    def __init__(self, test_list):
        self.test_queue = [t for t in reversed(test_list)]
        self._subtest_parent_map = {}
        self._tag_prefix_map = {}
        for test in test_list:
            if not isinstance(test, AutomatedSequence):
                self._tag_prefix_map[test] = test.kbd_shortcut
                continue
            step_count = 1
            for subtest in test.subtest_list:
                self._subtest_parent_map[subtest] = test
                if not isinstance(subtest, FactoryAutotestTest):
                    continue
                tag_prefix = ('%s_s%d' % (test.subtest_tag_prefix, step_count))
                self._tag_prefix_map[subtest] = tag_prefix
                step_count += 1
        self.seq_test_set = set(test for test in test_list
                                if isinstance(test, AutomatedSequence))
        self.subtest_set = set(reduce(lambda x, y: x + y,
                                      [test.subtest_list for test in
                                       self.seq_test_set], []))
        self._subtest_map = dict((self._tag_prefix_map[st], st)
                                 for st in self.subtest_set)
        self.all_tests = set(test_list) | self.subtest_set
        self._unique_name_map = dict((t.unique_name, t) for t in self.all_tests
                                     if isinstance(t, FactoryAutotestTest)
                                     and t.unique_name is not None)
        self._unique_details_map = dict((self.get_unique_details(t), t)
                                        for t in self.all_tests)
        self._kbd_shortcut_map = dict((test.kbd_shortcut, test)
                                      for test in test_list)
        self.kbd_shortcut_set = set(self._kbd_shortcut_map)

        # Validate keyboard shortcut uniqueness.
        assert(None not in self.kbd_shortcut_set)
        delta = set(test_list) - set(self._kbd_shortcut_map.values())
        for test in delta:
            collision = kbd_shortcut_map[test.kbd_shortcut]
            log('ERROR: tests %s and %s both have kbd_shortcut %s' %
                (test.label_en, collision.label_en, test.kbd_shortcut))
        assert not delta

    def get_tag_prefix(self, test):
        return self._tag_prefix_map[test]

    def get_unique_details(self, test):
        if isinstance(test, AutomatedSequence):
            return test.subtest_tag_prefix
        return '%s.%s' % (test.autotest_name, self.get_tag_prefix(test))

    def get_test_by_unique_details(self, autotest_name, tag_prefix):
        unique_details = '%s.%s' % (autotest_name, tag_prefix)
        return self._unique_details_map.get(unique_details)

    def get_test_by_kbd_shortcut(self, kbd_shortcut):
        return self._kbd_shortcut_map.get(kbd_shortcut)

    def get_test_by_unique_name(self, unique_name):
        return self._unique_name_map.get(unique_name)

    def get_subtest_parent(self, test):
        return self._subtest_parent_map.get(test)

    def get_subtest_by_tag_prefix(self, tag_prefix):
        return self._subtest_map.get(tag_prefix)


class StatusMap:

    class Entry:

        def __init__(self):
            self.status = UNTESTED
            self.count = 0
            self.label_box = None
            self.error_msg = None

    def __init__(self, test_list, status_file_path):
        self.test_db = TestDatabase(test_list)
        all_tests = self.test_db.all_tests
        self._status_map = dict((t, StatusMap.Entry()) for t in all_tests)
        self._status_file_path = status_file_path
        self._status_file_pos = 0
        self.read_new_data()

    def lookup_status(self, test):
        return self._status_map[test].status

    def lookup_count(self, test):
        return self._status_map[test].count

    def lookup_label_box(self, test):
        return self._status_map[test].label_box

    def lookup_error_msg(self, test):
        return self._status_map[test].error_msg

    def lookup_tag(self, test):
        tag_prefix = self.test_db.get_tag_prefix(test)
        count = self._status_map[test].count
        return '%s_%s' % (tag_prefix, count)

    def incr_count(self, test):
        self._status_map[test].count += 1

    def filter(self, target_status):
        comp = (isinstance(target_status, list) and
                (lambda s: s in target_status) or
                (lambda s: s == target_status))
        return [t for t in self.test_db.test_queue
                if comp(self.lookup_status(t))]

    def next_untested(self):
        remaining = self.filter(UNTESTED)
        unique_details = [self.test_db.get_unique_details(t) for t in remaining]
        log('remaining untested = [%s]' % ', '.join(unique_details))
        return remaining is not [] and remaining.pop() or None

    def read_new_data(self):
        with open(self._status_file_path) as file:
            file.seek(self._status_file_pos)
            for line in file:
                cols = line.strip().split('\t') + ['']
                code = cols[0]
                test_id = cols[1]
                if code not in STATUS_CODE_MAP or test_id == '----':
                    continue
                status = STATUS_CODE_MAP[code]
                error_msg = status == FAILED and cols[len(cols) - 2] or None
                log('reading code = %s, test_id = %s, error_msg = "%s"'
                    % (code, test_id, error_msg))
                autotest_name, _, tag = test_id.rpartition('.')
                tag_prefix, _, count = tag.rpartition('_')
                test = self.test_db.get_test_by_unique_details(
                    autotest_name, tag_prefix)
                if test is None:
                    log('ignoring update (%s) for test "%s" "%s"' %
                        (status, autotest_name, tag_prefix))
                    continue
                self.update(test, status, int(count), error_msg)
                map(self.update_seq_test, self.test_db.seq_test_set)
            self._status_file_pos = file.tell()

    def get_active_top_level_test(self):
        active_tests = set(self.filter(ACTIVE)) - self.test_db.subtest_set
        return active_tests and active_tests.pop() or None

    def get_active_subtest(self):
        active_subtests = set(self.filter(ACTIVE)) & self.test_db.subtest_set
        return active_subtests and active_subtests.pop() or None

    def register_active(self, test):
        active_tests = set(self.filter(ACTIVE))
        assert(test not in active_tests)
        if test in self.test_db.subtest_set:
            parent_seq_test = self.test_db.get_subtest_parent(test)
            active_tests -= set([parent_seq_test])
        for bad_test in active_tests:
            unique_details = self.test_db.get_unique_details(bad_test)
            log('WARNING: assuming test %s FAILED (status log has no data)' %
                unique_details)
            self.update(bad_test, FAILED, self.lookup_count(bad_test),
                        'assumed FAILED (status log has no data)')

    def update(self, test, status, count, error_msg):
        entry = self._status_map[test]
        unique_details = self.test_db.get_unique_details(test)
        if count < entry.count:
            log('ERROR: count regression for %s (%d -> %d)' %
                (unique_details, entry.count, count))
        if isinstance(test, InformationScreen) and status in [PASSED, FAILED]:
            status = UNTESTED
        if status != entry.status:
            log('status change for %s : %s/%s -> %s/%s' %
                (unique_details, entry.status, entry.count, status, count))
            if entry.label_box is not None:
                entry.label_box.update(status)
            if status == ACTIVE:
                self.register_active(test)
        entry.status = status
        entry.count = count
        entry.error_msg = error_msg
        log('%s new status = %s' %
            (unique_details, self._status_map[test].status))

    def update_seq_test(self, test):
        subtest_status_set = set(map(self.lookup_status, test.subtest_list))
        max_count = max(map(self.lookup_count, test.subtest_list))
        if len(subtest_status_set) == 1:
            status = subtest_status_set.pop()
        elif subtest_status_set == set([PASSED, FAILED]):
            status = FAILED
        else:
            status = ACTIVE
        self.update(test, status, max_count, None)

    def set_label_box(self, test, label_box):
        entry = self._status_map[test]
        entry.label_box = label_box
        label_box.update(entry.status)


class LogData:

    def __init__(self):
        self._log_file_pos = 0
        self.shared_dict = {}
        self.read_new_data()

    def read_new_data(self):
        with open(LOG_PATH) as file:
            file.seek(self._log_file_pos)
            for line in file:
                parts = line.rsplit(DATA_PREFIX, 1)
                if not len(parts) == 2:
                    continue
                key, raw_value = parts.pop().strip().split('=', 1)
                log('updating shared_dict[%s]=%s' % (key, raw_value))
                self.shared_dict[key] = eval(raw_value)
            self._log_file_pos = file.tell()

    def get(self, key):
        return self.shared_dict.get(key)


class ControlState:

    def __init__(self, job, test_list, status_map, status_file_path, nuke_fn):
        self._job = job
        self._status_map = status_map
        self._log_data = LogData()
        self._std_dargs = {
            'status_file_path' : status_file_path,
            'test_list': test_list}
        self._nuke_fn = nuke_fn
        self.activated_kbd_shortcut_test = None
        signal.signal(signal.SIGUSR1, self.kill_current_test_callback)

        log('waiting for ui to come up...')
        while self._log_data.get('test_widget_size') is None:
            time.sleep(1)
            self._log_data.read_new_data()

    def kill_current_test_callback(self, signum, frame):
        self._log_data.read_new_data()
        active_test_data = self._log_data.get('active_test_data')
        log('KILLING active_test_data %s' % repr(active_test_data))
        if active_test_data is not None:
            self._nuke_fn(*active_test_data)

    def run_test(self, test):
        self._status_map.incr_count(test)
        self._log_data.read_new_data()
        test_tag = self._status_map.lookup_tag(test)
        dargs = {}
        dargs.update(test.dargs)
        dargs.update(self._std_dargs)
        dargs.update({'tag': test_tag,
                      'subtest_tag': test_tag,
                      'shared_dict': self._log_data.shared_dict})

        self._job.factory_shared_dict = self._log_data.shared_dict

        log('control shared dict = %s' % repr(self._log_data.shared_dict))

        if test.drop_caches:
            self._job.drop_caches_between_iterations = True
        self.activated_kbd_shortcut_test = None

        self._job.run_test(test.autotest_name, **dargs)

        self._job.drop_caches_between_iterations = False
        self._log_data.read_new_data()
        kbd_shortcut = self._log_data.shared_dict.pop(
            'activated_kbd_shortcut', None)
        if kbd_shortcut is not None:
            test_db = self._status_map.test_db
            target_test = test_db.get_test_by_kbd_shortcut(kbd_shortcut)
            self.activated_kbd_shortcut_test = target_test
            log('kbd_shortcut %s -> %s)' % (
                kbd_shortcut, test_db.get_unique_details(target_test)))
