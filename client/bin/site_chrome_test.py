# Copyright (c) 2010 The Chromium OS Authors. All rights reserved.
# Use of this source code is governed by a BSD-style license that can be
# found in the LICENSE file.

import logging, os, re, shutil, subprocess, tempfile, utils
from autotest_lib.client.cros import constants, login
from autotest_lib.client.bin import test
from autotest_lib.client.common_lib import error, global_config
from autotest_lib.client.cros import ui

class ChromeTestBase(test.test):
    home_dir = None

    def setup(self):
        self.job.setup_dep(['chrome_test'])
        # create a empty srcdir to prevent the error that checks .version file
        if not os.path.exists(self.srcdir):
            os.mkdir(self.srcdir)


    def initialize(self):
        self.home_dir = tempfile.mkdtemp()
        dep = 'chrome_test'
        dep_dir = os.path.join(self.autodir, 'deps', dep)
        self.job.install_pkg(dep, 'dep', dep_dir)
        self.cr_source_dir = '%s/test_src' % dep_dir
        self.test_binary_dir = '%s/out/Release' % self.cr_source_dir
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


    def filter_bad_tests(self, tests):
        matcher = re.compile(".+\.(FLAKY|FAILS|DISABLED).+")
        return filter(lambda(x): not matcher.match(x), tests)


    def list_chrome_tests(self, test_binary):
        all_tests = []
        try:
            cmd = '%s/%s --gtest_list_tests' % (self.test_binary_dir,
                                                test_binary)
            cmd = 'HOME=%s CR_SOURCE_ROOT=%s %s' % (self.home_dir,
                                                    self.cr_source_dir,
                                                    ui.xcommand(cmd))
            logging.debug("Running %s" % cmd)
            test_proc = subprocess.Popen(cmd,
                                         shell=True,
                                         stdout=subprocess.PIPE)
            last_suite = None
            skipper = re.compile('YOU HAVE')
            for line in test_proc.stdout:
                stripped = line.lstrip()
                if stripped == '' or skipper.match(stripped):
                    continue
                elif (stripped == line):
                    last_suite = stripped.rstrip()
                else:
                  all_tests.append(last_suite+stripped.rstrip())
        except OSError, e:
            logging.debug(e)
            raise error.TestFail('Failed to list tests in %s!' % test_binary)
        return all_tests


    def run_chrome_test(self, test_to_run, extra_params=''):
        try:
            cmd = '%s/%s %s' % (self.test_binary_dir, test_to_run, extra_params)
            cmd = 'HOME=%s CR_SOURCE_ROOT=%s %s' % (self.home_dir,
                                                    self.cr_source_dir,
                                                    ui.xcommand(cmd))
            utils.system(cmd)
        except error.CmdError, e:
            logging.debug(e)
            raise error.TestFail('%s failed!' % test_to_run)


    def generate_test_list(self, binary, group, total_groups):
        all_tests = self.list_chrome_tests(self.binary_to_run)
        group_size = len(all_tests)/total_groups + 1  # to be safe
        return all_tests[group*group_size:group*group_size+group_size]


    def cleanup(self):
        # Allow chrome to be restarted again.
        os.unlink(constants.DISABLE_BROWSER_RESTART_MAGIC_FILE)
        # Reset the UI.
        login.nuke_login_manager()
        login.refresh_login_screen()
        if self.home_dir:
            shutil.rmtree(self.home_dir, ignore_errors=True)
        test.test.cleanup(self)
