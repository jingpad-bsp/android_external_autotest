#!/usr/bin/env python
# Copyright (c) 2010 The Chromium OS Authors. All rights reserved.
# Use of this source code is governed by a BSD-style license that can be
# found in the LICENSE file.


'''
This module provides both client and server side of a XML RPC based server which
can be used to handle factory test states(status) and shared persistent data.

To start the server, simply invoke this module as a standalone program.

Clients can use factory_state.get_instance() for a proxy stub object to send
requests to server. Examples:
    instance = factory_state.get_instance()
    instance.register_tests(['a', 'b', 'c'], 'UNTESTED')
    instance.increase_test_count('a')
    instance.set_shared('test1:param1', '0')
    print instance.lookup_test_status('a')
    print instance.get_shared('test1:param1')

See help(factory_state.StateServer) for more information.
'''


import SimpleXMLRPCServer
import os
import pprint
import sys
import xmlrpclib


DEFAULT_FACTORY_STATE_PORT = 0x0FAC
DEFAULT_FACTORY_STATE_ADDRESS = 'localhost'
DEFAULT_FACTORY_STATE_BIND_ADDRESS = 'localhost'
DEFAULT_FACTORY_STATE_FILE = '/var/log/factory_state'

KEY_STATUS = 'status'
KEY_COUNT = 'count'
KEY_ERROR_MSG = 'error_msg'
KEY_UNIQUE_NAME = 'unique_name'

DICT_TEST_STATUS = 'test_status'
DICT_SHARED_DATA = 'shared_data'


class StateServer(object):
    '''
    The core implementation for factory state control.
    The major provided features are:

    SHARED DATA
        You can get/set simple data into the states and share between all tests.
        See get_shared(name) and set_shared(name, value) for more information.

        If you need to get all shared data (or updating multiple entries at
        once), see get_shared_dict() and update_shared_dict.

    TEST STATUS
        To track the execution status of factory auto tests, you need to first
        register the complete list of your tests by invoking
        register_tests(list, status).  Then you can use lookup_test_status(id),
        lookup_test_count(id), lookup_test_error_msg(id) to query various state
        information of a list.

        To modify the state of a test, use increase_test_count(id) and
        update_test_status(id, status, error_msg).

    See help(StateServer.[methodname]) for more information.
    '''
    VERSION = 1

    def __init__(self, state_file_path=None):
        '''
        Initializes the state server.

        Parameters:
            state_file_path:    External file to store the state information.
        '''
        if not state_file_path:
            state_file_path = '%s.v%s' % (DEFAULT_FACTORY_STATE_FILE,
                                          self.VERSION)
        self._state_file_path = state_file_path
        self._test_status = {}
        self._shared_data = {}
        self.reload()

    def reload(self):
        '''
        Loads state from external file storage.

        Returns:
            True if the state is loaded successfully, otherwise False.
        '''
        if not os.path.exists(self._state_file_path):
            return False
        try:
            with open(self._state_file_path, 'r') as f:
                # TODO(hungte) use pickle instead
                blob = eval(f.read())
            self._test_status = blob[DICT_TEST_STATUS]
            self._shared_data = blob[DICT_SHARED_DATA]
            return True
        except:
            print 'Error: failed to reload from', self._state_file_path
            return False

    def flush(self):
        '''
        Saves current state to external file storage.

        Returns:
            True if the data was saved successfully, otherwise False.
        '''
        try:
            # TODO(hungte) write to some temporary file first for atomic flush
            with open(self._state_file_path, 'w') as f:
                blob = {}
                blob[DICT_TEST_STATUS]= self._test_status
                blob[DICT_SHARED_DATA]= self._shared_data
                f.write(pprint.pformat(blob))
            return True
        except:
            return False


    # Shared data (public data pool for factory tests to share)

    def get_shared_dict(self):
        ''' Returns the whole shared data as a dictionary object. '''
        # When being used as a remote server, the return data is always a copy
        # to client instead of live references.
        return self._shared_data

    def update_shared_dict(self, newdict):
        '''
        Updates the shared data by a dictionary object.

        Returns:
            True if the updates are saved successfully, otherwise False.
        '''
        self._shared_data.update(newdict)
        return self.flush()

    def get_shared(self, name):
        '''
        Returns the shared data associated by name
        (None if the name has not been set with any value).
        '''
        return self._shared_data.get(name, None)

    def set_shared(self, name, value):
        '''
        Sets the shared data of name to value.

        Returns:
            True if the changes are saved successfully, otherwise False.
        '''
        self._shared_data[name] = value
        return self.flush()


    # Test Status (dedicated for factory test system)

    def register_tests(self, test_unique_id_list, init_status):
        '''
        Declares the list of tests by test_unique_id_list.
        If there's already a list defined in state server, merge the lists.

        Parameters:
            test_unique_id_list: a list of tests' unique id list.
            init_status: the initial status for newly added tests.

        Returns:
            True if the list has been changed, otherwise False.
        '''
        is_modified = False
        del_list = [k for k in self._test_status if k not in
                    test_unique_id_list]
        for k in del_list:
            del self._test_status[k]
            is_modified = True
        for test_id in test_unique_id_list:
            if test_id in self._test_status:
                continue
            self.update_test_status(test_id, init_status)
            is_modified = True
        return self.flush() if is_modified else False

    def clear_all_tests(self):
        '''
        Clears all existing tests in state server.

        Returns:
            True if the change is saved successfully, otherwise False.
        '''
        self._test_status = {}
        return self.flush()

    def get_all_tests(self):
        '''
        Returns the complete test list and their current status as a dictionary.
        '''
        return dict((k, v.get(KEY_STATUS, None))
                    for k, v in self._test_status.items())

    def update_test_status(self, test_unique_id, status, error_msg=None):
        '''
        Updates the status of a test.

        Parameters:
            test_unique_id: The id of test to update.
            status:         The new status code.
            error_msg:      Optional error message.

        Returns:
            True if the change is saved successfully, otherwise False.
        '''
        entry = {
            KEY_STATUS: status,
            KEY_ERROR_MSG: error_msg,
        }
        # TODO(hungte) we can reduce flush frequency by checking if the new
        # status is really different.
        if test_unique_id not in self._test_status:
            entry[KEY_COUNT] = 0
            self._test_status[test_unique_id] = entry
        else:
            self._test_status[test_unique_id].update(entry)
        return self.flush()

    def lookup_test_status(self, test_unique_id):
        '''
        Looks up the execution status of a test specified by test_unique_id.

        Parameters:
            test_unique_id: The unique id string of target test.

        Returns:
            Execution status if test_unique_id is valid, otherwise None.
        '''
        if test_unique_id not in self._test_status:
            return None
        return self._test_status[test_unique_id].get(KEY_STATUS, None)

    def lookup_test_status_by_unique_name(self, test_unique_name):
        '''
        Looks up the execution status of a test referred by unique name
        (must be set by set_test_unique_name).

        Parameters:
            test_unique_name: The unique name associated with target test.

        Returns:
            Execution status if test_unique_name is valid, otherwise None.
        '''
        assert test_unique_name, "Unique name must be a non-empty string"
        for test in self._test_status.values():
            if KEY_UNIQUE_NAME in test:
                return test[KEY_UNIQUE_NAME]
        return None

    def lookup_test_count(self, test_unique_id):
        '''
        Looks up how many times a test is executed. See increase_test_count.

        Parameters:
            test_unique_id: The unique id string of target test.

        Returns:
            Number of executions if test_unique_id is valid, otherwise None.
        '''
        if test_unique_id not in self._test_status:
            return None
        return self._test_status[test_unique_id].get(KEY_COUNT, 0)

    def lookup_test_error_msg(self, test_unique_id):
        '''
        Looks up the error message of a test.

        Parameters:
            test_unique_id: The unique id string of target test.

        Returns:
            Last error message if test_unique_id is valid, otherwise None.
        '''
        return self._test_status[test_unique_id].get(KEY_ERROR_MSG, None)

    def increase_test_count(self, test_unique_id):
        '''
        Increases the execution counter of a test. See lookup_test_count.

        Parameters:
            test_unique_id: The unique id string of target test.

        Returns:
            True if the counter is increased, otherwise False.
        '''
        assert test_unique_id in self._test_status
        count = self.lookup_test_count(test_unique_id)
        self._test_status[test_unique_id][KEY_COUNT] = count + 1
        return self.flush()

    def set_test_unique_name(self, test_unique_id, test_unique_name):
        '''
        Assigns a "unique name" property to a list.

        Parameters:
            test_unique_id: The unique id of test to set.
            test_unique_name: The name

        Returns:
            True if the list has been changed, otherwise False.
        '''
        if test_unique_id not in self._test_status:
            return False
        self._test_status[test_unique_id][KEY_UNIQUE_NAME] = test_unique_name
        return self.flush()


def get_instance(address=DEFAULT_FACTORY_STATE_ADDRESS,
                 port=DEFAULT_FACTORY_STATE_PORT):
    '''
    Gets an instance (for client side) to access the state server.

    Parameters:
        address:    Address of the server to be connected.
        port:       Port of the server to be connected.

    Returns:
        An object with all public functions from StateServer.
        See help(StateServer) for more information.
    '''
    return xmlrpclib.ServerProxy('http://%s:%d' % (address, port),
                                 allow_none=True, verbose=False)


def run_as_server(file_path=None, bind_address=None, port=None):
    '''
    Starts a factory state server.

    Parameters:
        file_path:      File to store (and reload) the state information.
        bind_address:   The address for server to bind.
        port:           The port for server to bind.

    Returns:
        Never returns if the server is started successfully, otherwise
        some exception will be raised.
    '''
    if not bind_address:
        bind_address = DEFAULT_FACTORY_STATE_BIND_ADDRESS
    if not port:
        port = DEFAULT_FACTORY_STATE_PORT
    instance = StateServer(file_path)
    server = SimpleXMLRPCServer.SimpleXMLRPCServer((bind_address, port),
                                                   allow_none=True,
                                                   logRequests=False)
    server.register_introspection_functions()
    server.register_instance(instance)
    print "Factory State Server started in http://%s:%s" % (bind_address, port)
    # The printing of message and flushing to stdout (usually as pipe) is to
    # signal parent process that server is ready.
    sys.stdout.flush()
    server.serve_forever()


def main(argv):
    ''' Main entry when being invoked by command line. '''
    file_path = None
    argc = len(argv)
    # TODO(hungte) support address/port from command line
    if argc == 2:
        file_path = argv[1]
    elif argc > 2:
        print "usage: %s [state_file_path]" % argv[0]
        sys.exit(1)
    run_as_server(file_path)


if __name__ == '__main__':
    main(sys.argv)
