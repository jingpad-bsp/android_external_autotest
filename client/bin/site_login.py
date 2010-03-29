# Copyright (c) 2010 The Chromium OS Authors. All rights reserved.
# Use of this source code is governed by a BSD-style license that can be
# found in the LICENSE file.

import logging, os, utils, signal, time
from autotest_lib.client.bin import chromeos_constants, site_cryptohome, test
from autotest_lib.client.common_lib import error, site_ui


def setup_autox(test):
    test.job.setup_dep(['autox'])
    # create a empty srcdir to prevent the error that checks .version file
    if not os.path.exists(test.srcdir):
        os.mkdir(test.srcdir)


def logged_in():
    # this file is created when the session_manager emits start-user-session
    # and removed when the session_manager emits stop-user-session
    return os.path.exists(chromeos_constants.LOGGED_IN_MAGIC_FILE)


def attempt_login(test, script_file, timeout=10):
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


def attempt_logout(timeout=10):
    # Gracefully exiting chrome causes the user's session to end.
    utils.system('pkill -TERM -o ^%s$' % chromeos_constants.BROWSER)
    start_time = time.time()
    while time.time() - start_time < timeout:
        if not logged_in():
            break
        time.sleep(1)
    else:
        return False
    return True


def wait_for_browser(timeout=10):
    # Wait until the login manager is back up before trying to use it.
    # I don't use utils.system here because I don't want to fail
    # if pgrep returns non-zero, I just want to wait and try again.
    start_time = time.time()
    while time.time() - start_time < timeout:
        # 0 is returned on success.
        if os.system('pgrep ^%s$' % chromeos_constants.BROWSER) == 0:
            break;
        time.sleep(1)
    else:
        return False
    return True


def wait_for_cryptohome(timeout=10):
    start_time = time.time()
    while time.time() - start_time < timeout:
        if site_cryptohome.is_mounted():
            break;
        time.sleep(1)
    else:
        return False
    return True


def wait_for_screensaver(timeout=10, raise_error=True):
    # Wait until the screensaver starts
    start_time = time.time()
    while time.time() - start_time < timeout:
        if 0 == os.system(site_ui.xcommand('xscreensaver-command -version')):
            break
        time.sleep(1)
    else:
        if raise_error:
            raise error.TestFail('Unable to communicate with ' +
                                 'xscreensaver after %i seconds' %
                                 time.time() - start_time)
        return False

    return True


def wait_for_window_manager(timeout=20):
    """Wait until the window manager is running."""
    start_time = time.time()
    while time.time() - start_time < timeout:
        if os.system('pgrep ^%s$' % chromeos_constants.WINDOW_MANAGER) == 0:
            return True
        time.sleep(0.1)
    return False


def nuke_login_manager():
    nuke_process_by_name('session_manager')
    wait_for_browser()


def nuke_process_by_name(name, with_prejudice=False):
    pid = int(utils.system_output('pgrep -o ^%s$' % name))
    if with_prejudice:
        utils.nuke_pid(pid, [signal.SIGKILL])
    else:
        utils.nuke_pid(pid)
