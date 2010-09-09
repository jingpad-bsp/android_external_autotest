# Copyright (c) 2010 The Chromium OS Authors. All rights reserved.
# Use of this source code is governed by a BSD-style license that can be
# found in the LICENSE file.


# DESCRIPTION :
#
# This library provides common types and routines for the factory ui
# infrastructure.  This library explicitly does not import gtk, to
# allow its use by the autotest control process.


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

class AutomatedRebootSubTest(AutomatedSubTest):
    def __init__(self, label_en='', label_zw='', iterations=None,
                 autotest_name='factory_RebootStub', dargs={},
                 drop_caches=False, unique_name=None):
        self.__dict__.update(vars())


class KbdShortcutDatabase:
    '''Track the bindings between keyboard shortcuts and tests.'''

    def __init__(self, test_list, test_db):
        self._kbd_shortcut_map = dict(
            (test.kbd_shortcut, test) for test in test_list)

        # Validate keyboard shortcut uniqueness.
        assert(None not in self._kbd_shortcut_map)
        delta = set(test_list) - set(self._kbd_shortcut_map.values())
        for test in delta:
            collision = kbd_shortcut_map[test.kbd_shortcut]
            log('ERROR: tests %s and %s both have kbd_shortcut %s' %
                (test_db.get_unique_id_str(test),
                 test_db.get_unique_id_str(collision),
                 test.kbd_shortcut))
        assert not delta

    def get_shortcut_keys(self):
        return set(self._kbd_shortcut_map)

    def lookup_test(self, kbd_shortcut):
        return self._kbd_shortcut_map.get(kbd_shortcut)


class TestDatabase:
    '''This class parses a test_list and allows searching for tests or
    their attributes.  It also generates tag_prefix values for each
    runnable test.  Autotest allows tests with the same name to be
    uniquely identified by the "tag" parameter to the job.run_test()
    function.  The factory system generates this value as the
    combination of a tag_prefix value and a counter that tracks how
    many times a test has run.  Tests are identified uniquely in the
    status log by both the tag_prefix and their autotest name.  These
    values are referred to here as the unique_details for the test.'''

    def __init__(self, test_list):
        self._test_list = test_list
        self._subtest_set = set()
        self._subtest_parent_map = {}
        self._tag_prefix_map = {}
        for test in test_list:
            if not isinstance(test, AutomatedSequence):
                self._tag_prefix_map[test] = test.kbd_shortcut
                continue
            step_count = 1
            for subtest in test.subtest_list:
                self._subtest_parent_map[subtest] = test
                self._subtest_set.add(subtest)
                if not isinstance(subtest, FactoryAutotestTest):
                    continue
                tag_prefix = ('%s_s%d' % (test.subtest_tag_prefix, step_count))
                self._tag_prefix_map[subtest] = tag_prefix
                step_count += 1
        self._tag_prefix_to_subtest_map = dict(
            (self._tag_prefix_map[st], st) for st in self._subtest_set)
        self._unique_details_map = dict(
            (self.get_unique_details(t), t) for t in self.get_all_tests()
            if isinstance(t, FactoryAutotestTest))
        self._unique_name_map = dict(
            (t.unique_name, t) for t in self.get_all_tests()
            if getattr(t, 'unique_name', None) is not None)

    def get_test_by_unique_details(self, autotest_name, tag_prefix):
        return self._unique_details_map.get((autotest_name, tag_prefix))

    def get_tag_prefix(self, test):
        return self._tag_prefix_map[test]

    def get_unique_details(self, test):
        return (test.autotest_name, self.get_tag_prefix(test))

    def get_test_by_unique_name(self, unique_name):
        return self._unique_name_map.get(unique_name)

    def get_subtest_parent(self, test):
        return self._subtest_parent_map.get(test)

    def get_subtest_by_tag_prefix(self, tag_prefix):
        return self._tag_prefix_to_subtest_map.get(tag_prefix)

    def get_automated_sequences(self):
        return [test for test in self._test_list
                if isinstance(test, AutomatedSequence)]

    def get_all_tests(self):
        return set(self._test_list) | self._subtest_set

    def get_unique_id_str(self, test):
        '''Intended primarily to identify tests for debugging.'''
        if test is None:
            return None
        if isinstance(test, AutomatedSequence):
            return test.subtest_tag_prefix
        return '%s.%s' % self.get_unique_details(test)


class StatusMap:
    '''Parse the contents of an autotest status file for factory tests
    into a database containing status, count, and error message
    information.  On __init__ the status file is parsed once.  Changes
    to the file are dealt with by running read_new_data().  Complexity
    is introduced here because AutomatedSequences are not directly
    represented in the status file and their status must be derived
    from subtest results.'''

    class Entry:

        def __init__(self):
            self.status = UNTESTED
            self.count = 0
            self.error_msg = None

    def __init__(self, test_list, status_file_path, test_db=None,
                 status_change_callback=None):
        self._test_list = [test for test in test_list]
        self._test_db = test_db if test_db else TestDatabase(test_list)
        self._status_map = dict(
            (test, StatusMap.Entry()) for test in self._test_db.get_all_tests())
        self._status_file_path = status_file_path
        self._status_file_pos = 0
        self._active_automated_seq = None
        self._status_change_callback = status_change_callback
        self.read_new_data()

    def lookup_status(self, test, min_count=0):
        entry = self._status_map[test]
        return entry.status if entry.count >= min_count else UNTESTED

    def lookup_count(self, test):
        if isinstance(test, AutomatedSubTest):
            parent = self._test_db.get_subtest_parent(test)
            return self._status_map[parent].count
        else:
            return self._status_map[test].count

    def lookup_error_msg(self, test):
        return self._status_map[test].error_msg

    def filter_by_status(self, target_status):
        comp = (isinstance(target_status, list) and
                (lambda s: s in target_status) or
                (lambda s: s == target_status))
        return [test for test in self._test_db.get_all_tests()
                if comp(self.lookup_status(test))]

    def next_untested(self):
        for test in self._test_list:
            if self.lookup_status(test) == UNTESTED:
                return test
        return None

    def get_active_top_level_test(self):
        if self._active_automated_seq:
            return self._active_automated_seq
        active_tests = [test for test in self._test_list
                        if self.lookup_status(test) == ACTIVE]
        if len(active_tests) > 1:
            log('ERROR -- multiple active top level tests %s' %
                repr([self._test_db.get_unique_id_str(test)
                      for test in active_tests]))
        return active_tests.pop() if active_tests != [] else None

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
                autotest_name, _, tag = test_id.rpartition('.')
                tag_prefix, _, count = tag.rpartition('_')
                test = self._test_db.get_test_by_unique_details(
                    autotest_name, tag_prefix)
                if test is None:
                    log('status map ignoring update (%s) for test %s %s' %
                        (status, repr(autotest_name), repr(tag_prefix)))
                    continue
                self.update(test, status, int(count), error_msg)
            self._status_file_pos = file.tell()

    def update(self, test, status, count, error_msg):
        entry = self._status_map[test]
        unique_id_str = self._test_db.get_unique_id_str(test)
        if count < entry.count:
            log('ignoring older data for %s (data count %d < state count  %d)' %
                (unique_id_str, count, entry.count))
            return
        if isinstance(test, InformationScreen) and status in [PASSED, FAILED]:
            status = UNTESTED
        parent_as = self._test_db.get_subtest_parent(test)
        if status != entry.status:
            log('status change for %s : %s/%s -> %s/%s (as = %s)' %
                (unique_id_str, entry.status, entry.count, status,
                 count, self._test_db.get_unique_id_str(parent_as)))
            if self._status_change_callback is not None:
                self._status_change_callback(test, status)
        entry.status = status
        entry.count = count
        entry.error_msg = error_msg
        if (status == ACTIVE and not isinstance(test, AutomatedSequence) and
            self._active_automated_seq != parent_as):
            if self._active_automated_seq is not None:
                self.update_automated_sequence(self._active_automated_seq)
            self._active_automated_seq = parent_as
        if parent_as is not None:
            self.update_automated_sequence(parent_as)

    def update_automated_sequence(self, test):
        max_count = max([self._status_map[st].count
                         for st in test.subtest_list])
        lookup_fn = lambda x: self.lookup_status(x, min_count=max_count)
        subtest_status_set = set(
            self.lookup_status(subtest) for subtest in test.subtest_list)
        log('automated sequence %s status set = %s' % (
            self._test_db.get_unique_id_str(test),
            repr(subtest_status_set)))
        if len(subtest_status_set) == 1:
            status = subtest_status_set.pop()
        elif (test == self._active_automated_seq and
              FAILED not in subtest_status_set):
            status = ACTIVE
        else:
            status = FAILED
        self.update(test, status, max_count, None)


class LogData:
    '''Parse the factory log looking for specially formatted
    name-value declarations and recording the last of any such
    bindings in a dict.  Data in the right format is written to the
    log using log_shared_data().'''

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
    '''Track the state needed to run and terminate factory tests.  The
    shared data written to the factory log records the pid information
    for each test as it gets run.  If the factory UI sees a keyboard
    shortcut event, it sends a SIGUSR1 event to the control process,
    which then uses the log information to terminate the running
    test.'''

    def __init__(self, job, test_list, test_db, status_map,
                 status_file_path, nuke_fn):
        self._job = job
        self._status_map = status_map
        self._kbd_shortcut_db = KbdShortcutDatabase(test_list, test_db)
        self._test_db = test_db
        self._log_data = LogData()
        self._std_dargs = {
            'status_file_path' : status_file_path,
            'test_list': test_list}
        self._nuke_fn = nuke_fn
        signal.signal(signal.SIGUSR1, self.kill_current_test_callback)

    def kill_current_test_callback(self, signum, frame):
        self._log_data.read_new_data()
        active_test_data = self._log_data.get('active_test_data')
        if active_test_data is not None:
            log('SIGUSR1 ... KILLING active test %s' % repr(active_test_data))
            self._nuke_fn(*active_test_data)
        else:
            log('SIGUSR1 ... KILLING NOTHING, no active test')

    def process_kbd_shortcut_activation(self):
        kbd_shortcut = self._log_data.get('activated_kbd_shortcut')
        if kbd_shortcut is None:
            return None
        target_test = self._kbd_shortcut_db.lookup_test(kbd_shortcut)
        log('activated kbd_shortcut %s -> %s' % (
            kbd_shortcut, self._test_db.get_unique_id_str(target_test)))
        log_shared_data('activated_kbd_shortcut', None)
        return target_test

    def run_test(self, test, count):
        self._log_data.read_new_data()
        test_tag = '%s_%s' % (self._test_db.get_tag_prefix(test), count)
        dargs = {}
        dargs.update(test.dargs)
        dargs.update(self._std_dargs)
        dargs.update({'tag': test_tag,
                      'subtest_tag': test_tag,
                      'shared_dict': self._log_data.shared_dict})
        self._job.factory_shared_dict = self._log_data.shared_dict
        self._job.drop_caches_between_iterations = test.drop_caches
        self._job.run_test(test.autotest_name, **dargs)
        self._job.drop_caches_between_iterations = False
        self._log_data.read_new_data()
        return self.process_kbd_shortcut_activation()


def lookup_status_by_unique_name(unique_name, test_list, status_file_path):
    """Determine the status of given test.  Somewhat heavyweight,
    since it parses the status file."""
    test_db = TestDatabase(test_list)
    test = test_db.get_test_by_unique_name(unique_name)
    return StatusMap(test_list, status_file_path, test_db).lookup_status(test)
