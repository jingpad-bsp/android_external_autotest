# Copyright (c) 2010 The Chromium OS Authors. All rights reserved.
# Use of this source code is governed by a BSD-style license that can be
# found in the LICENSE file.

import logging, os, utils, signal, time
from autotest_lib.client.bin import chromeos_constants, site_cryptohome
from autotest_lib.client.bin import site_utils, test
from autotest_lib.client.common_lib import error, site_ui


class TimeoutError(error.TestError):
  """Error returned if we time out while waiting on a condition."""
  pass


def setup_autox(test):
    test.job.setup_dep(['autox'])
    # create a empty srcdir to prevent the error that checks .version file
    if not os.path.exists(test.srcdir):
        os.mkdir(test.srcdir)


def logged_in():
    # this file is created when the session_manager emits start-user-session
    # and removed when the session_manager emits stop-user-session
    return os.path.exists(chromeos_constants.LOGGED_IN_MAGIC_FILE)


# TODO: Update this to use the Python-based autox instead.
def attempt_login(test, script_file, timeout=10):
    """Attempt to log in.

    Args:
        script: str filename of autox JSON script
        timeout: float number of seconds to wait

    Raises:
        error.TestFail: autox program exited with failure
        TimeoutError: login didn't complete before timeout
    """
    dep = 'autox'
    dep_dir = os.path.join(test.autodir, 'deps', dep)
    test.job.install_pkg(dep, 'dep', dep_dir)

    autox_binary = '%s/%s' % (dep_dir, 'autox')
    autox_script = os.path.join(test.job.configdir, script_file)

    # TODO: Use something more robust that checks whether the login window is
    # mapped.
    wait_for_browser()
    try:
        utils.system(site_ui.xcommand('%s %s' % (autox_binary, autox_script)))
    except error.CmdError, e:
        logging.debug(e)
        raise error.TestFail('AutoX program failed to login for test user')

    site_utils.poll_for_condition(
        lambda: logged_in(),
        TimeoutError('Timed out while waiting to be logged in'),
        timeout=timeout)


def attempt_logout(timeout=10):
    """Attempt to log out by killing Chrome.

    Args:
        timeout: float number of seconds to wait

    Raises:
        TimeoutError: logout didn't complete before timeout
    """
    # Gracefully exiting chrome causes the user's session to end.
    wait_for_initial_chrome_window()
    utils.system('pkill -TERM -o ^%s$' % chromeos_constants.BROWSER)
    site_utils.poll_for_condition(
        lambda: not logged_in(),
        TimeoutError('Timed out while waiting for logout'),
        timeout=timeout)


def wait_for_browser(timeout=10):
    """Wait until a Chrome process is running.

    Args:
        timeout: float number of seconds to wait

    Raises:
        TimeoutError: Chrome didn't start before timeout
    """
    site_utils.poll_for_condition(
        lambda: os.system('pgrep ^%s$' % chromeos_constants.BROWSER) == 0,
        TimeoutError('Timed out waiting for Chrome to start'),
        timeout=timeout)


def wait_for_cryptohome(timeout=10):
    """Wait until cryptohome is mounted.

    Args:
        timeout: float number of seconds to wait

    Raises:
        TimeoutError: cryptohome wasn't mounted before timeout
    """
    site_utils.poll_for_condition(
        lambda: site_cryptohome.is_mounted(),
        TimeoutError('Timed out waiting for cryptohome to be mounted'),
        timeout=timeout)


def wait_for_screensaver(timeout=10):
    """Wait until xscreensaver is responding.

    Args:
        timeout: float number of seconds to wait

    Raises:
        TimeoutError: xscreensaver didn't respond before timeout
    """
    site_utils.poll_for_condition(
        lambda: os.system(
            site_ui.xcommand('xscreensaver-command -version')) == 0,
        TimeoutError('Timed out waiting for xscreensaver to respond'),
        timeout=timeout)


def wait_for_window_manager(timeout=20):
    """Wait until the window manager is running.

    Args:
        timeout: float number of seconds to wait

    Raises:
        TimeoutError: window manager didn't start before timeout
    """
    site_utils.poll_for_condition(
        lambda: not os.system('pgrep ^%s$' % chromeos_constants.WINDOW_MANAGER),
        TimeoutError('Timed out waiting for window manager to start'),
        timeout=timeout)


def wait_for_initial_chrome_window(timeout=20):
    """Wait until the initial Chrome window is mapped.

    Args:
      timeout: float number of seconds to wait

    Raises:
        TimeoutError: Chrome window wasn't mapped before timeout
    """
    site_utils.poll_for_condition(
        lambda: os.access(
            chromeos_constants.CHROME_WINDOW_MAPPED_MAGIC_FILE, os.F_OK),
        TimeoutError('Timed out waiting for initial Chrome window'),
        timeout=timeout)


def nuke_login_manager():
    nuke_process_by_name('session_manager')
    wait_for_browser()


def nuke_process_by_name(name, with_prejudice=False):
    pid = int(utils.system_output('pgrep -o ^%s$' % name))
    if with_prejudice:
        utils.nuke_pid(pid, [signal.SIGKILL])
    else:
        utils.nuke_pid(pid)
