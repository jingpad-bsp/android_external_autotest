# Copyright (c) 2012 The Chromium OS Authors. All rights reserved.
# Use of this source code is governed by a BSD-style license that can be
# found in the LICENSE file.

"""Base class for using Chrome PyAuto Automation in autotest tests.

This class takes care of getting the automation framework ready for work.

Things this class does:
  - Enable automation and restart chrome with appropriate flags
  - Log in to default account

The PyAuto framework must be installed on the machine for this to work,
under .../autotest/deps/{pyauto_dep|chrome_test}/test_src/chrome/pyautolib'.
This is built by the chromeos-chrome ebuild.
"""

import logging, os, shutil, subprocess, sys
from optparse import OptionParser

import common, constants, cros_ui, cryptohome
from autotest_lib.client.bin import test, utils
from autotest_lib.client.common_lib import error


class PyAutoTest(test.test):
    """Base autotest class for tests which require the PyAuto framework.

    Inherit this class to make calls to the PyUITest framework.

    Each test begins with a clean browser profile. (ie clean /home/chronos).
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
    def __init__(self, *args, **kwargs):
        self._dep = 'pyauto_dep'
        # Handle to pyauto, for chrome automation.
        self.pyauto = None
        self.pyauto_suite = None

        test.test.__init__(self, *args, **kwargs)


    def use_chrome_deps(self):
      self._dep = 'chrome_test'


    def setup(self):
      self.job.setup_dep([self._dep])


    def _install_deps(self):
        """Set up deps needed for running pyauto."""
        dep_dir = os.path.join(self.autodir, 'deps', self._dep)
        self.job.install_pkg(self._dep, 'dep', dep_dir)

        # Make pyauto importable.
        # This can be done only after chrome_test/pyauto_dep dependency has been
        # installed.
        pyautolib_dir = os.path.join(
            dep_dir, 'test_src', 'chrome', 'test', 'pyautolib')
        if not os.path.isdir(pyautolib_dir):
            raise error.TestError('%s missing.' % pyautolib_dir)
        sys.path.append(pyautolib_dir)

        # TODO(frankf): This should be done automatically by setup_dep.
        # Create symlinks to chrome
        test_binary_dir = os.path.join(
            dep_dir, 'test_src', 'out', 'Release')
        try:
            setup_cmd = '/bin/bash %s/%s' % (test_binary_dir,
                                             'setup_test_links.sh')
            utils.system(setup_cmd)  # this might raise an exception
        except error.CmdError, e:
            raise error.TestError(e)
        self._setup_suid_python(test_binary_dir)


    def _setup_suid_python(self, test_binary_dir):
        """Setup suid python which can enable chrome testing interface.

        This is required when running pyauto as non-privileged user (chronos).
        """
        suid_python = os.path.join(test_binary_dir, 'suid-python')
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


    def _get_pyuitest_class(self, class_name):
        """Obtains a object reference of a class with the indicated name.
        Assumes pyauto deps has already been installed.

        Args:
          class_name: string in <package>.<class> format that represents
                      the PYUITest to be used (eg. 'policy_base.PolicyBaseTest')

        Returns:
          An instance of pyauto.PyUITest.
        """
        import pyauto
        module, _, name = class_name.rpartition('.')
        mod = getattr(__import__(module), name)
        assert issubclass(mod, pyauto.PyUITest), '%s is not a subclass of ' \
                                                 'PyUITest' % name
        return mod


    def initialize(self, auto_login=True, extra_chrome_flags=[],
                   subtract_extra_chrome_flags=[],
                   pyuitest_class='pyauto.PyUITest', *args, **kwargs):
        """Initialize.

        Expects session_manager to be alive.

        Args:
            auto_login: should we auto login using $default account?
            extra_chrome_flags: Extra chrome flags to pass to chrome, if any.
            subtract_extra_chrome_flags: Remove default flags passed to chrome
                by pyauto, if any.
        """
        assert os.geteuid() == 0, 'Need superuser privileges'

        self._install_deps()
        import pyauto

        pyauto_class = self._get_pyuitest_class(pyuitest_class)

        class PyUITestInAutotest(pyauto_class):
            """Adaptation of PyUITest for use in Autotest."""
            def runTest(self):
                # unittest framework expects runTest.
                pass

            def ShouldOOBESkipToLogin(self):
                return False

            def ShouldAutoLogin(self):
                # Do not auto login
                return False

            def ExtraChromeFlags(self):
                args = pyauto_class.ExtraChromeFlags(self)
                return list((set(args) - set(subtract_extra_chrome_flags))
                            | set(extra_chrome_flags))

        parser = OptionParser()
        pyauto._OPTIONS, args = parser.parse_args([])
        pyauto._OPTIONS.channel_id = ''
        pyauto._OPTIONS.no_http_server = True
        pyauto._OPTIONS.remote_host = None

        self.pyauto_suite = pyauto.PyUITestSuite(
            ['--ui-test-action-timeout=60000',
             '--ui-test-action-max-timeout=60000'])
        self.pyauto = PyUITestInAutotest()

        # Enable chrome testing interface and log in to default account
        self.pyauto.setUp()  # connects to pyauto automation
        if auto_login:
            self.pyauto.SkipToLogin()
            self.LoginToDefaultAccount()


    def LoginToDefaultAccount(self):
        """Login to ChromeOS using $default testing account."""
        creds = constants.CREDENTIALS['$default']
        username = cryptohome.canonicalize(creds[0])
        passwd = creds[1]
        err_mesg = self.pyauto.Login(username, passwd)
        if err_mesg or not self.pyauto.GetLoginInfo()['is_logged_in']:
             raise error.TestError(
                 'Error during Login(%s): %s' % (username, err_mesg))
        logging.info('Logged in as %s' % username)


    def cleanup(self):
        """Clean up after running the test.

        We restart chrome and restart the login manager
        """
        if self.pyauto:
            self.pyauto.tearDown()
            del self.pyauto
        if self.pyauto_suite:
            del self.pyauto_suite

        # Reset the UI.
        cros_ui.restart()

        test.test.cleanup(self)
