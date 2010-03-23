# Copyright (c) 2010 The Chromium OS Authors. All rights reserved.
# Use of this source code is governed by a BSD-style license that can be
# found in the LICENSE file.

import logging, os, utils, time
from autotest_lib.client.bin import test
from autotest_lib.client.common_lib import error, site_ui

def setup_autox(test):
    test.job.setup_dep(['autox'])
    # create a empty srcdir to prevent the error that checks .version file
    if not os.path.exists(test.srcdir):
        os.mkdir(test.srcdir)

def logged_in():
    # this file is created when the session_manager emits start-user-session
    # and removed when the session_manager emits stop-user-session
    return os.path.exists("/var/run/state/logged-in")

def attempt_login(test, script_file, timeout = 10):
    dep = 'autox'
    dep_dir = os.path.join(test.autodir, 'deps', dep)
    test.job.install_pkg(dep, 'dep', dep_dir)

    autox_binary = '%s/%s' % (dep_dir, 'autox')
    autox_script = os.path.join(test.job.configdir, script_file)

    try:
        utils.system(site_ui.xcommand('%s %s' % (autox_binary, autox_script)))
    except error.CmdError, e:
        logging.debug(e)
        raise error.TestFail('AutoX program failed to login for test user')

    start_time = time.time()
    while time.time() - start_time < timeout:
        if logged_in():
            break
        time.sleep(1)
    else:
        return False
    return True

def attempt_logout(timeout = 10):
    # Gracefully exiting chrome causes the user's session to end.
    utils.system('pkill -TERM ^chrome$')
    start_time = time.time()
    while time.time() - start_time < timeout:
        if not logged_in():
            break
        time.sleep(1)
    else:
        return False
    return True

def wait_for_login_manager(timeout = 10):
    # Wait until the login manager is back up before trying to use it.
    # I don't use utils.system here because I don't want to fail
    # if pgrep returns non-zero, I just want to wait and try again.
    start_time = time.time()
    while time.time() - start_time < timeout:
        if os.system('pgrep ^chrome$'):
            break;
        time.sleep(1)
    else:
        return False
    return True

def nuke_login_manager():
    pid = int(utils.system_output('pgrep -o ^session_manager$'))
    utils.nuke_pid(pid)
    wait_for_login_manager()
