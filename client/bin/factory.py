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
import factory_state


ACTIVE = 'ACTIVE'
PASSED = 'PASS'
FAILED = 'FAIL'
UNTESTED = 'UNTESTED'

LOG_PATH = '/var/log/factory.log'
DATA_PREFIX = 'FACTORY_DATA:'
FINAL_VERIFICATION_TEST_UNIQUE_NAME = 'factory_Verify'
REVIEW_INFORMATION_TEST_UNIQUE_NAME = 'ReviewInformation'

_state_instance = None


def log(s):
    print >> sys.stderr, 'FACTORY: ' + s

def get_state_instance():
    ''' A quick way to get a (cached) instance for factory_state '''
    global _state_instance
    if _state_instance is None:
        _state_instance = factory_state.get_instance()
    return _state_instance

def get_shared_data(key):
    return get_state_instance().get_shared(key)

def set_shared_data(key, value):
    return get_state_instance().set_shared(key, value)

def log_shared_data(key, value):
    ''' (for backward compatibility) Same as set_shared_data '''
    return set_shared_data(key, value)


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
        self._unique_id_str_map = dict(
            (self.get_unique_id_str(t), t) for t in self.get_all_tests())

    def get_test_by_unique_details(self, autotest_name, tag_prefix):
        return self._unique_details_map.get((autotest_name, tag_prefix))

    def get_tag_prefix(self, test):
        return self._tag_prefix_map[test]

    def get_unique_details(self, test):
        return (test.autotest_name, self.get_tag_prefix(test))

    def get_test_by_unique_name(self, unique_name):
        return self._unique_name_map.get(unique_name)

    def get_test_by_unique_id_str(self, unique_id_str):
        return self._unique_id_str_map.get(unique_id_str)

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
    '''
    Manipulates the status of factory tests by providing query and set
    operations to the status, counter, and error messages associated with tests
    in test database, by wrapping calls to factory_state.
    '''

    def __init__(self, test_list, status_file_path, test_db=None,
                 status_change_callback=None):
        self._state = get_state_instance()
        self._test_list = [test for test in test_list]
        self._test_db = test_db if test_db else TestDatabase(test_list)
        self._status_change_callback = status_change_callback

    def lookup_status(self, test):
        return self._state.lookup_test_status(
                self._test_db.get_unique_id_str(test))

    def lookup_count(self, test):
        return self._state.lookup_test_count(
                self._test_db.get_unique_id_str(test))

    def increase_count(self, test):
        return self._state.increase_test_count(
                self._test_db.get_unique_id_str(test))

    def lookup_error_msg(self, test):
        return self._state.lookup_test_error_msg(
                self._test_db.get_unique_id_str(test))

    def filter_by_status(self, target_status):
        # TODO(hungte) use self._state.filter_by_status?
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
        assert False, "not supported yet"

    def _do_update(self, test, status, error_msg=None):
        if isinstance(test, InformationScreen) and (status in [PASSED, FAILED]):
            status = UNTESTED
        unique_id_str = self._test_db.get_unique_id_str(test)
        last_status = self.lookup_status(test)
        if status != last_status:
            parent_as = self._test_db.get_subtest_parent(test)
            log('status change for %s : %s -> %s (as = %s)' %
                (unique_id_str, last_status, status,
                 self._test_db.get_unique_id_str(parent_as)))
            self._state.update_test_status(unique_id_str, status, error_msg)
            if self._status_change_callback is not None:
                self._status_change_callback(test, status)

    def update(self, test, status, error_msg=None):
        ''' Updates the status information of a factory test.
        If parameter 'test' is a AutomatedSubTest, also update its parent. '''
        parent_as = self._test_db.get_subtest_parent(test)
        self._do_update(test, status, error_msg)
        if isinstance(parent_as, AutomatedSequence):
            self.update_automated_sequence(parent_as, test)

    def update_automated_sequence(self, test, sub_test):
        rst_index = test.subtest_list.index(sub_test) + 1
        for sub_test in test.subtest_list[rst_index:]:
            if self.lookup_status(sub_test) != UNTESTED:
                self._do_update(sub_test, UNTESTED)
        subtest_status_set = set(self.lookup_status(subtest)
                                 for subtest in test.subtest_list)
        log('automated sequence %s status set = %s' % (
            self._test_db.get_unique_id_str(test), repr(subtest_status_set)))
        if len(subtest_status_set) == 1:
            status = subtest_status_set.pop()
        elif FAILED not in subtest_status_set:
            status = ACTIVE
        else:
            status = FAILED
        self._do_update(test, status)


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
        self._std_dargs = {
            'status_file_path' : status_file_path,
            'test_list': test_list}
        self._nuke_fn = nuke_fn
        signal.signal(signal.SIGUSR1, self.kill_current_test_callback)

    def kill_current_test_callback(self, signum, frame):
        active_test_data = get_shared_data('active_test_data')
        if active_test_data is not None:
            log('SIGUSR1 ... KILLING active test %s' % repr(active_test_data))
            self._nuke_fn(*active_test_data)
        else:
            log('SIGUSR1 ... KILLING NOTHING, no active test')

    def process_fail_or_kbd_shortcut_activation(self, last_status=None):
        kbd_shortcut = get_shared_data('activated_kbd_shortcut')
        if kbd_shortcut is None:
            if last_status != FAILED:
                return None
            log('last test failed, routing to review screen...')
            return self._test_db.get_test_by_unique_name(
                REVIEW_INFORMATION_TEST_UNIQUE_NAME)
        target_test = self._kbd_shortcut_db.lookup_test(kbd_shortcut)
        log('activated kbd_shortcut %s -> %s' % (
            kbd_shortcut, self._test_db.get_unique_id_str(target_test)))
        log_shared_data('activated_kbd_shortcut', None)
        return target_test

    def run_test(self, test, count=None):
        if count == None:
            count = self._status_map.lookup_count(test)
            self._status_map.increase_count(test)
        test_tag = '%s_%s' % (self._test_db.get_tag_prefix(test), count)
        dargs = {}
        dargs.update(test.dargs)
        dargs.update(self._std_dargs)
        # TODO(hungte) we should deprecate shared_dict in dargs and use
        # factory.get_shared_data / set_shared_data
        dargs.update({'tag': test_tag,
                      'subtest_tag': test_tag,
                      'shared_dict': get_state_instance().get_shared_dict()})
        self._job.drop_caches_between_iterations = test.drop_caches
        self._status_map.update(test, ACTIVE, None)
        status = FAILED
        error_msg = None
        if self._job.run_test(test.autotest_name, **dargs):
            status = PASSED
        elif hasattr(self._job, 'last_error'):
            error_msg = str(self._job.last_error)
        self._status_map.update(test, status, error_msg)
        self._job.drop_caches_between_iterations = False
        return self.process_fail_or_kbd_shortcut_activation(status)


def lookup_status_by_unique_name(unique_name, test_list, _=None):
    """Determine the status of given test.  Somewhat heavyweight,
    since it parses the status file."""
    # TODO(hungte) we should deprecate this function and use StatusMap or
    # factory_state to query directly.
    test_db = TestDatabase(test_list)
    test = test_db.get_test_by_unique_name(unique_name)
    unique_id = test_db.get_unique_id_str(test)
    return get_state_instance().lookup_test_status(unique_id)
