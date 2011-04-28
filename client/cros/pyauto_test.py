# Copyright (c) 2011 The Chromium Authors. All rights reserved.
# Use of this source code is governed by a BSD-style license that can be
# found in the LICENSE file.

"""Base class for running PyAuto tests.

This class takes care of getting the automation framework ready for work.

Things this class handles:
- Restart Chrome with appropriate flags
- Set up an suid python for running pyauto
- Start up PyUITestSuite
- Log in to default account

After the test completes this class shuts chrome down and restarts things
as they were before.

The PyAuto framework must be installed on the machine for this to work,
under .../autotest/deps/chrome_test/test_src/chrome/pyautolib'. This is
built by the Chrome ebuild.

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
from autotest_lib.client.cros import constants, login
from autotest_lib.client.common_lib import error
from autotest_lib.client.bin import utils


class PyAutoTest(test.test):
    """Base autotest class for tests which require the PyAuto framework.

    Inherit this class to make calls to the PyUITest framework.

    For example:
        from autotest_lib.client.cros import pyauto_test

        class desktopui_UrlFetch(pyauto_test.PyAutoTest):
            version = 1

            def run_once(self):
                self.pyauto.NavigateToURL('http://www.google.com')

    """
    def __init__(self, job, bindir, outputdir):
        test.test.__init__(self, job, bindir, outputdir)
        self.pyauto = None

    # from ChromeTestBase.initilize()
    def QuitChrome(self):
        try:
            open(constants.DISABLE_BROWSER_RESTART_MAGIC_FILE, 'w').close()
        except IOError, e:
            logging.debug(e)
            raise error.TestError('Failed to disable browser restarting.')
        login.nuke_process_by_name(name=constants.BROWSER, with_prejudice=True)
        try:
            setup_cmd = '/bin/sh %s/%s' % (self.test_binary_dir,
                                           'setup_test_links.sh')
            utils.system(setup_cmd)  # this might raise an exception
        except error.CmdError, e:
            raise error.TestError(e)

    # From chrome_test.ChromeTestBase.initialize(self)
    def SetupDeps(self):
        """Set up the directory paths we care about"""
        dep = 'pyauto_dep'
        self.dep_dir = os.path.join(self.autodir, 'deps', dep)
        self.job.install_pkg(dep, 'dep', self.dep_dir)

        # We use this strange directory because pyauto.py expects it
        self.test_binary_dir = '%s/bin' % self.dep_dir

    # From desktopui_PyAutoFunctionalTests.initialize()
    def SetupPython(self):
        # Setup suid python binary which can enable Chrome testing interface
        suid_python = os.path.join(self.test_binary_dir, 'python')
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

    # From desktopui_PyAutoFunctionalTests(chrome_test.ChromeTestBase):
    def initialize(self):
        assert os.geteuid() == 0, 'Need superuser privileges'
        self.SetupDeps()

        # This is needed because Chrome runs as chronos and so the automation
        # framework should run as the same uid.
        subprocess.check_call(['chown', '-R', 'chronos', self.test_binary_dir])

        self.QuitChrome()
        self.SetupPython()

        parser = OptionParser()

        # Import the pyauto module
        sys.path.append(os.path.join(os.path.dirname(__file__),
            os.pardir, 'deps', 'pyauto_dep', 'pyautolib'))
        try:
            import pyauto
        except ImportError:
            print >>sys.stderr, 'Cannot import pyauto from %s' % sys.path
            raise

        self.pyauto = pyauto.PyUITest()

        pyauto._OPTIONS, args = parser.parse_args([])
        pyauto._OPTIONS.channel_id = ''
        pyauto._OPTIONS.no_http_server = True

        suite_args = []
        self.pyauto_suite = pyauto.PyUITestSuite(suite_args)

        self.pyauto.setUp()

        # Enable chrome testing interface and log in to default account
        self.LoginToDefaultAccount()

    # These should perhaps move to a cros utilities library
    def LoginToDefaultAccount(self):
        """Login to ChromeOS using default testing account."""
        creds = constants.CREDENTIALS['$default']
        username = creds[0]
        passwd = creds[1]
        self.pyauto.Login(username, passwd)
        assert self.pyauto.GetLoginInfo()['is_logged_in']
        logging.info('Logged in as %s' % username)

    def cleanup(self):
        """Clean up after running the test.

        We restart chrome and restart the login manager
        """
        self.pyauto.tearDown()
        del self.pyauto_suite
        del self.pyauto

        # Allow chrome to be restarted again.
        os.unlink(constants.DISABLE_BROWSER_RESTART_MAGIC_FILE)

        # Reset the UI.
        login.nuke_login_manager()
        login.refresh_login_screen()

        test.test.cleanup(self)
