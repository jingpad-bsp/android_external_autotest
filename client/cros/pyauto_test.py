# Copyright (c) 2011 The Chromium Authors. All rights reserved.
# Use of this source code is governed by a BSD-style license that can be
# found in the LICENSE file.

"""Base class for using Chrome PyAuto Automation in autotest tests.

This class takes care of getting the automation framework ready for work.

Things this class does:
  - Enable automation and restart chrome with appropriate flags
  - Log in to default account

The PyAuto framework must be installed on the machine for this to work,
under .../autotest/deps/pyauto_dep/test_src/chrome/pyautolib'. This is
built by the chromeos-chrome ebuild.
"""

import logging
from optparse import OptionParser
import os
import shutil
import stat
import subprocess
import sys
import tempfile

from autotest_lib.client.bin import test
from autotest_lib.client.cros import constants, cryptohome, login
from autotest_lib.client.common_lib import error
from autotest_lib.client.bin import utils


class PyAutoTest(test.test):
    """Base autotest class for tests which require the PyAuto framework.

    Inherit this class to make calls to the PyUITest framework.

    Each test begins with a clean browser profile. (ie clean local /home/chronos).
    For each test:
      - /home/chronos is cleared before firing up chrome
      - the default test user's cryptohome vault is cleared
      - login as default test user
    Beware however that:
      - chrome sync is still enabled, so the browser might fetch data/prefs over
        the air.
      - Settings not stored in /home/chronos might persist across tests

    Sample test:
        from autotest_lib.client.cros import pyauto_test

        class desktopui_UrlFetch(pyauto_test.PyAutoTest):
            version = 1

            def run_once(self):
                self.pyauto.NavigateToURL('http://www.google.com')
                self.assertEqual('Google', self.pyauto.GetActiveTabTitle)

    This test will login (with the default test account), then navigate to
    Google and verify its title.
    """
    def __init__(self, job, bindir, outputdir):
        test.test.__init__(self, job, bindir, outputdir)

        self._dep = 'pyauto_dep'
        self._dep_dir = os.path.join(self.autodir, 'deps', self._dep)
        self._test_binary_dir = '%s/test_src/out/Release' % self._dep_dir


    def SetupDeps(self):
        """Set up deps needed for running pyauto."""
        self.job.install_pkg(self._dep, 'dep', self._dep_dir)
        try:
            setup_cmd = '/bin/sh %s/%s' % (self._test_binary_dir,
                                           'setup_test_links.sh')
            utils.system(setup_cmd)  # this might raise an exception
        except error.CmdError, e:
            raise error.TestError(e)
        self._SetupSuidPython()


    def _SetupSuidPython(self):
        """Setup suid python which can enable chrome testing interface.

        This is required when running pyauto as non-privileged user (chronos).
        """
        suid_python = os.path.join(self._test_binary_dir, 'suid-python')
        py_path = subprocess.Popen(['which', 'python'],
                                   stdout=subprocess.PIPE).communicate()[0]
        py_path = py_path.strip()
        assert os.path.exists(py_path), 'Could not find python'
        if os.path.islink(py_path):
            linkto = os.readlink(py_path)
            py_path = os.path.join(os.path.dirname(py_path), linkto)
        shutil.copy(py_path, suid_python)
        os.chown(suid_python, 0, 0)
        os.chmod(suid_python, 04755)


    def initialize(self):
        assert os.geteuid() == 0, 'Need superuser privileges'

        # Ensure there's no stale cryptohome from previous tests
        creds = constants.CREDENTIALS['$default']
        username = cryptohome.canonicalize(creds[0])
        cryptohome.remove_vault(username)

        # Reset the UI.
        login.nuke_login_manager()
        login.refresh_login_screen()

        self.SetupDeps()

        # Import the pyauto module
        # This can be done only after pyauto_dep dependency has been installed.
        pyautolib_dir = os.path.join(
            os.path.dirname(__file__), os.pardir, 'deps', 'pyauto_dep',
            'test_src', 'chrome', 'test', 'pyautolib')
        assert os.path.isdir(pyautolib_dir), '%s missing.' % pyautolib_dir
        sys.path.append(pyautolib_dir)
        import pyauto

        # PyUITest is setup to use the python unittest framework.
        # Adapt it to use in the context of autotest.
        class PyUITestInAutotest(pyauto.PyUITest):
          def runTest(self):
            # unittest framework expects runTest.
            pass

        parser = OptionParser()
        pyauto._OPTIONS, args = parser.parse_args([])
        pyauto._OPTIONS.channel_id = ''
        pyauto._OPTIONS.no_http_server = True
        pyauto._OPTIONS.remote_host = None

        self.pyauto_suite = pyauto.PyUITestSuite([])
        self.pyauto = PyUITestInAutotest()

        # Enable chrome testing interface and log in to default account
        self.pyauto.setUp()  # connects to pyauto automation
        self.LoginToDefaultAccount()


    def LoginToDefaultAccount(self):
        """Login to ChromeOS using $default testing account."""
        creds = constants.CREDENTIALS['$default']
        username = cryptohome.canonicalize(creds[0])
        passwd = creds[1]
        self.pyauto.Login(username, passwd)
        assert self.pyauto.GetLoginInfo()['is_logged_in']
        logging.info('Logged in as %s' % username)


    def cleanup(self):
        """Clean up after running the test.

        We restart chrome and restart the login manager
        """
        self.pyauto.tearDown()
        del self.pyauto
        del self.pyauto_suite

        # Reset the UI.
        login.nuke_login_manager()
        login.refresh_login_screen()

        test.test.cleanup(self)
