# Copyright (c) 2011 The Chromium OS Authors. All rights reserved.
# Use of this source code is governed by a BSD-style license that can be
# found in the LICENSE file.

import errno, logging, os, re, shutil, signal, subprocess, time
import common
import constants, cros_logging, cros_ui, cryptohome, ownership
from autotest_lib.client.bin import utils
from autotest_lib.client.common_lib import error


_DEFAULT_TIMEOUT = 90  # longer because we may be crash dumping now.

# Log messages used to signal when we're restarting UI. Used to detect
# crashes by cros_ui_test.UITest.
UI_RESTART_ATTEMPT_MSG = 'cros/login.py: Attempting StopSession...'
UI_RESTART_COMPLETE_MSG = 'cros/login.py: StopSession complete.'


class TimeoutError(error.TestError):
    """Error raised when we time out while waiting on a condition."""
    pass


class CrashError(error.TestError):
    """Error raised when a pertinent process crashes while waiting on
    a condition.
    """
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

    p = subprocess.Popen(["pgrep", "^%s$" % constants.SESSION_MANAGER],
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
            ax = cros_ui.get_autox()
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


def process_crashed(process, log_reader):
    """Checks the log watched by |log_reader| to see if a crash was reported
    for |process|.

    Returns True if so, False if not.
    """
    return log_reader.can_find('Received crash notification for %s' % process)


def wait_for_condition(condition, timeout_msg, timeout, process, log_reader,
                       crash_msg):
    try:
        utils.poll_for_condition(
            condition,
            TimeoutError(timeout_msg),
            timeout=timeout)
    except TimeoutError, e:
        # We could fail faster if necessary, but it'd be more complicated.
        if process_crashed(process, log_reader):
            logging.error(crash_msg)
            raise CrashError(crash_msg)
        else:
            raise e


def wait_for_browser(timeout=_DEFAULT_TIMEOUT):
    """Wait until a Chrome process is running.

    Args:
        timeout: float number of seconds to wait

    Raises:
        TimeoutError: Chrome didn't start before timeout
    """
    # Mark /var/log/messages now; we'll run through all subsequent log messages
    # if we couldn't start chrome to see if the browser crashed.
    log_reader = cros_logging.LogReader()
    log_reader.set_start_by_current()
    wait_for_condition(
        lambda: os.system('pgrep ^%s$' % constants.BROWSER) == 0,
        timeout_msg='Timed out waiting for Chrome to start',
        timeout=timeout,
        process='chrome',
        log_reader=log_reader,
        crash_msg='Chrome crashed while starting up.')


def wait_for_cryptohome(timeout=_DEFAULT_TIMEOUT):
    """Wait until cryptohome is mounted.

    Args:
        timeout: float number of seconds to wait

    Raises:
        TimeoutError: cryptohome wasn't mounted before timeout
    """
    # Mark /var/log/messages now; we'll run through all subsequent log messages
    # if we couldn't get the browser up to see if the browser crashed.
    log_reader = cros_logging.LogReader()
    log_reader.set_start_by_current()
    wait_for_condition(
        condition=lambda: cryptohome.is_mounted(),
        timeout_msg='Timed out waiting for cryptohome to be mounted',
        timeout=timeout,
        process='cryptohomed',
        log_reader=log_reader,
        crash_msg='cryptohomed crashed during mount attempt')


def wait_for_login_prompt(timeout=_DEFAULT_TIMEOUT):
    """Wait the login prompt is on screen and ready

    Args:
        timeout: float number of seconds to wait

    Raises:
        TimeoutError: Login prompt didn't get up before timeout
    """
    # Mark /var/log/messages now; we'll run through all subsequent log messages
    # if we couldn't get the browser up to see if the browser crashed.
    log_reader = cros_logging.LogReader()
    log_reader.set_start_by_current()
    wait_for_condition(
        condition=lambda: os.access(
            constants.LOGIN_PROMPT_READY_MAGIC_FILE, os.F_OK),
        timeout_msg='Timed out waiting for login prompt',
        timeout=timeout,
        process='chrome',
        log_reader=log_reader,
        crash_msg='Chrome crashed before the login prompt.')


def wait_for_window_manager(timeout=_DEFAULT_TIMEOUT):
    """Wait until the window manager is running.

    Args:
        timeout: float number of seconds to wait

    Raises:
        TimeoutError: window manager didn't start before timeout
    """
    utils.poll_for_condition(
        lambda: not os.system('pgrep ^%s$' % constants.WINDOW_MANAGER),
        TimeoutError('Timed out waiting for window manager to start'),
        timeout=timeout)


def wait_for_initial_chrome_window(timeout=_DEFAULT_TIMEOUT):
    """Wait until the initial Chrome window is mapped.

    Args:
      timeout: float number of seconds to wait

    Raises:
        TimeoutError: Chrome window wasn't mapped before timeout
    """
    # Mark /var/log/messages now; we'll run through all subsequent log messages
    # if we couldn't get the browser up to see if the browser crashed.
    log_reader = cros_logging.LogReader()
    log_reader.set_start_by_current()
    wait_for_condition(
        lambda: os.access(
            constants.CHROME_WINDOW_MAPPED_MAGIC_FILE, os.F_OK),
        'Timed out waiting for initial Chrome window',
        timeout=timeout,
        process='chrome',
        log_reader=log_reader,
        crash_msg='Chrome crashed before first tab rendered.')


def wait_for_ownership(timeout=constants.DEFAULT_OWNERSHIP_TIMEOUT):
    log_reader = cros_logging.LogReader()
    log_reader.set_start_by_current()
    wait_for_condition(
        condition=lambda: os.access(constants.OWNER_KEY_FILE, os.F_OK),
        timeout_msg='Timed out waiting for ownership',
        timeout=timeout,
        process=constants.BROWSER,
        log_reader=log_reader,
        crash_msg='Chrome crashed before ownership could be taken.')


def nuke_login_manager():
    nuke_process_by_name('session_manager')
    wait_for_browser()


def nuke_process_by_name(name, with_prejudice=False):
    try:
        pid = int(utils.system_output('pgrep -o ^%s$' % name).split()[0])
    except Exception as e:
        logging.error(e)
        return
    if with_prejudice:
        utils.nuke_pid(pid, [signal.SIGKILL])
    else:
        utils.nuke_pid(pid)


def refresh_window_manager(timeout=_DEFAULT_TIMEOUT):
    """Clear state that tracks what WM has done, kill it, and wait until
    the window manager is running.

    Args:
        timeout: float number of seconds to wait

    Raises:
        TimeoutError: window manager didn't start before timeout
    """
    os.unlink(constants.CHROME_WINDOW_MAPPED_MAGIC_FILE)
    nuke_process_by_name(constants.WINDOW_MANAGER)
    wait_for_window_manager()


def restart_session_manager():
    """Send StopSession dbus call to cause session_manager restart."""

    # Log what we're about to do to /var/log/messages. Used to log crashes later
    # in cleanup by cros_ui_test.UITest.
    utils.system('logger "%s"' % UI_RESTART_ATTEMPT_MSG)

    try:
        oldpid = __get_session_manager_pid()

        log_reader = cros_logging.LogReader()
        log_reader.set_start_by_current()

        # Gracefully exiting session manager causes the user's session to end.
        ownership.connect_to_session_manager().StopSession('')
        wait_for_condition(
            condition=lambda: __session_manager_restarted(oldpid),
            timeout_msg='Timed out waiting for session_manager restart',
            timeout=_DEFAULT_TIMEOUT,
            process='session_manager',
            log_reader=log_reader,
            crash_msg='session_manager crashed while restarting.')
    finally:
        utils.system('logger "%s"' % UI_RESTART_COMPLETE_MSG)
