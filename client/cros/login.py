# Copyright (c) 2011 The Chromium OS Authors. All rights reserved.
# Use of this source code is governed by a BSD-style license that can be
# found in the LICENSE file.

import logging, os
import constants, cros_logging, cros_ui, cryptohome
from autotest_lib.client.bin import utils
from autotest_lib.client.common_lib import error


class CrashError(error.TestError):
    """Error raised when a pertinent process crashes while waiting on
    a condition.
    """
    pass


class UnexpectedCondition(error.TestError):
    """Error raised when an expected precondition is not met."""
    pass


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
            utils.TimeoutError(timeout_msg),
            timeout=timeout)
    except utils.TimeoutError, e:
        # We could fail faster if necessary, but it'd be more complicated.
        if process_crashed(process, log_reader):
            logging.error(crash_msg)
            raise CrashError(crash_msg)
        else:
            raise e


def wait_for_browser(timeout=cros_ui.DEFAULT_TIMEOUT):
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


def wait_for_cryptohome(timeout=cros_ui.DEFAULT_TIMEOUT):
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


def wait_for_window_manager(timeout=cros_ui.DEFAULT_TIMEOUT):
    """Wait until the window manager is running.

    Args:
        timeout: float number of seconds to wait

    Raises:
        TimeoutError: window manager didn't start before timeout
    """
    utils.poll_for_condition(
        lambda: not os.system('pgrep ^%s$' % constants.WINDOW_MANAGER),
        utils.TimeoutError('Timed out waiting for window manager to start'),
        timeout=timeout)


def wait_for_initial_chrome_window(timeout=cros_ui.DEFAULT_TIMEOUT):
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


def refresh_window_manager(timeout=cros_ui.DEFAULT_TIMEOUT):
    """Clear state that tracks what WM has done, kill it, and wait until
    the window manager is running.

    Args:
        timeout: float number of seconds to wait

    Raises:
        TimeoutError: window manager didn't start before timeout
    """
    os.unlink(constants.CHROME_WINDOW_MAPPED_MAGIC_FILE)
    utils.nuke_process_by_name(constants.WINDOW_MANAGER)
    wait_for_window_manager()
