# Copyright (c) 2010 The Chromium OS Authors. All rights reserved.
# Use of this source code is governed by a BSD-style license that can be
# found in the LICENSE file.

import logging, os, utils, time
from autotest_lib.client.bin import test
from autotest_lib.client.common_lib import error

def setup_autox(test):
    test.job.setup_dep(['autox'])
    # create a empty srcdir to prevent the error that checks .version file
    if not os.path.exists(test.srcdir):
        os.mkdir(test.srcdir)

def logged_in():
    # this file is created when the session_manager emits start-user-session
    # and removed when the session_manager emits stop-user-session
    return os.path.exists("/var/run/state/logged-in")

def attempt_login(test, timeout = 10, script_file = 'autox_script.json'):
    dep = 'autox'
    dep_dir = os.path.join(test.autodir, 'deps', dep)
    test.job.install_pkg(dep, 'dep', dep_dir)

    # Set up environment to access login manager
    environment_vars = \
        'DISPLAY=:0.0 XAUTHORITY=/home/chronos/.Xauthority'

    autox_binary = '%s/%s' % (dep_dir, 'autox')
    autox_script = os.path.join(test.bindir, script_file)

    try:
        utils.system('%s %s %s' \
                     % (environment_vars, autox_binary, autox_script))
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
