# Copyright (c) 2010 The Chromium OS Authors. All rights reserved.
# Use of this source code is governed by a BSD-style license that can be
# found in the LICENSE file.

import logging, os, utils, signal, subprocess, time
from autotest_lib.client.bin import chromeos_constants, site_cryptohome
from autotest_lib.client.bin import site_utils, test
from autotest_lib.client.common_lib import error, site_ui


class TimeoutError(error.TestError):
    """Error raised when we time out while waiting on a condition."""
    pass


class UnexpectedCondition(error.TestError):
    """Error raised when an expected precondition is not met."""
    pass


def __get_session_manager_pid():
    """Determine the pid of the session manager.

    Returns:
        An integer indicating the current session manager pid, or None if
        it is not running.
    """

    p = subprocess.Popen(["pgrep", "^%s$" % chromeos_constants.SESSION_MANAGER],
                         stdout=subprocess.PIPE)
    ary = p.communicate()[0].split()
    return int(ary[0]) if ary else None


def __session_manager_restarted(oldpid):
    """Detect if the session manager has restarted.

    Args:
        oldpid: Integer indicating the last known pid of the session_manager.

    Returns:
        True if the session manager is running under a pid other than
        'oldpid', X is running, and there is a window displayed.
    """
    import autox

    newpid = __get_session_manager_pid()
    if newpid and newpid != oldpid:
        try:
            ax = site_ui.get_autox()
        except autox.Xlib.error.DisplayConnectionError:
            return False

        # When the session manager starts up there is a moment where we can
        # make a connection with autox, but there is no window displayed.  If
        # we start sending keystrokes at this point they get lost.  If we wait
        # for this window to show up, things go much smoother.
        wid = ax.get_top_window_id_at_point(0, 0)
        if not wid:
            return False

        # The login manager displays its widgetry in a second window centered
        # on the screen.  Waiting for this window to show up is also helpful.
        # TODO: perhaps the login manager should emit some more trustworthy
        # signal when it's ready to accept credentials.
        x, y = ax.get_screen_size()
        wid2 = ax.get_top_window_id_at_point(x / 2, y / 2)
        if wid == wid2:
            return False

        return True

    return False


def logged_in():
    # this file is created when the session_manager emits start-user-session
    # and removed when the session_manager emits stop-user-session
    return os.path.exists(chromeos_constants.LOGGED_IN_MAGIC_FILE)


def attempt_login(username, password, timeout=20):
    """Attempt to log in.

    Args:
        script: str filename of autox JSON script
        timeout: float number of seconds to wait

    Raises:
        TimeoutError: login didn't complete before timeout
        UnexpectedCondition: login manager is not running, or user is already
            logged in.
    """
    logging.info("Attempting to login using autox.py and (%s, %s)" %
                 (username, password))

    if not __get_session_manager_pid():
        raise UnexpectedCondition("Session manager is not running")

    if logged_in():
        raise UnexpectedCondition("Already logged in")

    ax = site_ui.get_autox()
    # navigate to login screen
    ax.send_hotkey("Ctrl+Alt+L")
    # focus username
    ax.send_hotkey("Alt+U")
    ax.send_text(username)
    # TODO(rginda): remove Tab after http://codereview.chromium.org/1390003
    ax.send_hotkey("Tab")
    # focus password
    ax.send_hotkey("Alt+P")
    ax.send_text(password)
    ax.send_hotkey("Return")

    site_utils.poll_for_condition(
        logged_in, TimeoutError('Timed out waiting for login'),
        timeout=timeout)


def attempt_logout(timeout=20):
    """Attempt to log out by killing Chrome.

    Args:
        timeout: float number of seconds to wait

    Raises:
        TimeoutError: logout didn't complete before timeout
        UnexpectedCondition: user is not logged in
    """
    if not logged_in():
        raise UnexpectedCondition('Already logged out')

    oldpid = __get_session_manager_pid()

    # Gracefully exiting the session manager causes the user's session to end.
    utils.system('pkill -TERM -o ^%s$' %  chromeos_constants.SESSION_MANAGER)

    site_utils.poll_for_condition(
        lambda: __session_manager_restarted(oldpid),
        TimeoutError('Timed out waiting for logout'),
        timeout)


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
        lambda: site_ui.xsystem('xscreensaver-command -version',
                                ignore_status=True) == 0,
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
