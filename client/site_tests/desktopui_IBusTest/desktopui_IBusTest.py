# Copyright (c) 2010 The Chromium OS Authors. All rights reserved.
# Use of this source code is governed by a BSD-style license that can be
# found in the LICENSE file.

import logging, os, time
from autotest_lib.client.bin import site_ui_test, test
from autotest_lib.client.common_lib import error, site_ui, utils

def wait_for_ibus_daemon_or_die(timeout=10):
    # Wait until ibus-daemon starts. ibus-daemon starts after a user
    # logs in (see src/platform/init for details), hence it's not
    # guaranteed that ibus-daemon is running when the test starts.
    start_time = time.time()
    while time.time() - start_time < timeout:
        if os.system('pgrep ^ibus-daemon$') == 0:  # Returns 0 on success.
            return
        time.sleep(1)
    raise error.TestFail('ibus-daemon is not running')


class desktopui_IBusTest(site_ui_test.UITest):
    version = 1
    preserve_srcdir = True

    def setup(self):
        self.job.setup_dep(['ibusclient'])


    def run_ibusclient(self, options):
        cmd = site_ui.xcommand_as('%s %s' % (self.exefile, options), 'chronos')
        return utils.system_output(cmd, retain_output=True)


    def test_reachable(self):
        out = self.run_ibusclient('check_reachable')
        if not 'YES' in out:
            raise error.TestFail('ibus-daemon is not reachable')


    def test_supported_engines(self):
        out = self.run_ibusclient('list_engines')
        engine_names = out.splitlines()
        # We expect these engines to exist.
        expected_engine_names = ['chewing', 'hangul', 'pinyin', 'm17n:ar:kbd']
        for expected_engine_name in expected_engine_names:
            if not expected_engine_name in engine_names:
                raise error.TestFail('Engine not found: ' +
                                     expected_engine_name)


    def test_config(self, type_name):
        out = self.run_ibusclient('set_config %s' % type_name)
        if not 'OK' in out:
            raise error.TestFail('Failed to set %s value to '
                                 'the ibus config service' % type_name)
        out = self.run_ibusclient('get_config %s' % type_name)
        if not 'OK' in out:
            raise error.TestFail('Failed to get %s value from '
                                 'the ibus config service' % type_name)
        out = self.run_ibusclient('unset_config')
        if not 'OK' in out:
            raise error.TestFail('Failed to unset %s value from '
                                 'the ibus config service' % type_name)
        out = self.run_ibusclient('get_config %s' % type_name)
        # the value no longer exists.
        if 'OK' in out:
            raise error.TestFail('Failed to unset %s value from '
                                 'the ibus config service' % type_name)


    def run_once(self):
        wait_for_ibus_daemon_or_die()
        dep = 'ibusclient'
        dep_dir = os.path.join(self.autodir, 'deps', dep)
        self.job.install_pkg(dep, 'dep', dep_dir)

        self.exefile = os.path.join(self.autodir,
                                    'deps/ibusclient/ibusclient')
        self.test_reachable()
        self.test_supported_engines()
        for type_name in ['boolean', 'int', 'double', 'string']:
            self.test_config(type_name)
