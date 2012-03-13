# Copyright (c) 2012 The Chromium OS Authors. All rights reserved.
# Use of this source code is governed by a BSD-style license that can be
# found in the LICENSE file.

import logging
import os
import socket
import subprocess
import sys
import time

from autotest_lib.client.bin import test
from autotest_lib.client.common_lib import error

class security_HtpdateHTTP(test.test):
    """Implements regression tests for Date header parsing in htpdate."""
    version = 1
    _PORT = 19998
    _FLAG = '/var/run/HtpdateHTTP'
    _MAX_FLAG_WAIT = 10
    _MAX_RECV = 1024
    _HTPDATE_BIN = '/usr/sbin/htpdate'
    # Test cases taken from http://crosbug.com/8941#c3.
    _TESTS = {
              'No Date Header': 'HTTP/1.1 200 OK\r\n\r\n',
              'Empty Date': 'HTTP/1.1 200 OK\r\nDate: \r\n\r\n',
              'No GMT':
              'HTTP/1.1 200 OK\r\nDate: Wed, 14 Mar 2012 17:11:52\r\n\r\n',
              'No Seconds':
              'HTTP/1.1 200 OK\r\nDate: Wed, 14 Mar 2012 17:11:\r\n\r\n',
              'No Minutes':
              'HTTP/1.1 200 OK\r\nDate: Wed, 14 Mar 2012 17:\r\n\r\n',
              'No Hours':
              'HTTP/1.1 200 OK\r\nDate: Wed, 14 Mar 2012\r\n\r\n',
              'No Year':
              'HTTP/1.1 200 OK\r\nDate: Wed, 14 Mar\r\n\r\n',
              'No Month':
              'HTTP/1.1 200 OK\r\nDate: Wed, 14\r\n\r\n',
              'Single Digit Day':
              'HTTP/1.1 200 OK\r\nDate: Wed, 7 Mar 2012 17:11:52 GMT\r\n\r\n',
              'Multi Digit Day < 10':
              'HTTP/1.1 200 OK\r\nDate: Wed, 07 Mar 2012 17:11:52 GMT\r\n\r\n',
              'Multi Digit Day > 10':
              'HTTP/1.1 200 OK\r\nDate: Wed, 14 Mar 2012 17:11:52 GMT\r\n\r\n',
             }

    def wait_on_flag(self, flag_file, max_checks):
        for i in range(max_checks):
            if os.path.exists(flag_file):
                return True
            else:
                time.sleep(1)
        return os.path.exists(flag_file)


    def test_case(self, test_name, test_data):
        pid = os.fork()
        if (pid):
            # We're in the parent. Spin until the child is ready for us,
            # otherwise we might race and launch htpdate before the
            # listener is set up.
            if not self.wait_on_flag(self._FLAG, self._MAX_FLAG_WAIT):
                raise error.TestFail('Listener never showed up.')

            proc = subprocess.Popen([self._HTPDATE_BIN, '-q', '-d',
                                     'localhost:'+str(self._PORT)])
            retcode = proc.wait()
            logging.debug('Test case %s: Exit status: %d' %
                          (test_name, retcode))
            if retcode < 0:
                raise error.TestFail('Crashed during %s.' % test_name)

        else:
            # We're in the child. Note that while it might seem
            # inefficient to set up and tear down this socket per-test
            # in an entirely seperate process, testing shows this has
            # some important stability consequences for the test
            # itself. Htpdate in some - but not all - cases will
            # attempt 2 consecutive connections, and we get long hangs
            # during the second attempt if the listening process has
            # not exited. Tearing down the listener from within the
            # long-lived python process is apparently not sufficient
            # to get the connection attempt refused quickly, so we do
            # it in a child that we can exit entirely.
            server = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
            server.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
            server.bind(('localhost', self._PORT))
            server.listen(0)
            # Touch the flagfile to let the parent know the listen is up.
            file(self._FLAG, 'a').close()
            sock, address = server.accept()
            junk = sock.recv(self._MAX_RECV)
            sock.send(test_data)
            sock.shutdown(socket.SHUT_RDWR)
            sock.close()
            os.unlink(self._FLAG)
            sys.exit(0)


    def run_once(self):
        for test_name, test_data in self._TESTS.items():
            self.test_case(test_name, test_data)
