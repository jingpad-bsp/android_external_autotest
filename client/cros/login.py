# Copyright (c) 2012 The Chromium OS Authors. All rights reserved.
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


def wait_for_condition(condition, timeout_msg, timeout, process, crash_msg):
    # Mark /var/log/messages now; we'll run through all subsequent log
    # messages if we couldn't start chrome to see if the browser crashed.
    log_reader = cros_logging.LogReader()
    log_reader.set_start_by_current()
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
    wait_for_condition(
        lambda: os.system('pgrep ^%s$ >/dev/null' % constants.BROWSER) == 0,
        timeout_msg='Timed out waiting for Chrome to start',
        timeout=timeout,
        process=constants.BROWSER,
        crash_msg='Chrome crashed while starting up.')


def wait_for_browser_exit(crash_msg, timeout=cros_ui.DEFAULT_TIMEOUT):
    """Wait for the Chrome process to exit.

    Args:
        crash_msg: Error message to include if Chrome crashed.
        timeout: float number of seconds to wait

    Returns:
        True if Chrome exited; False otherwise.

    Raises:
        CrashError: Chrome crashed while we were waiting.
    """
    try:
      wait_for_condition(
          lambda: os.system('pgrep ^%s$ >/dev/null' % constants.BROWSER) != 0,
          timeout_msg='Timed out waiting for Chrome to exit',
          timeout=timeout,
          process=constants.BROWSER,
          crash_msg=crash_msg)
      return True
    except utils.TimeoutError, e:
      return False


def wait_for_cryptohome(user, timeout=cros_ui.DEFAULT_TIMEOUT):
    """Wait until cryptohome is mounted.

    Args:
        timeout: float number of seconds to wait

    Raises:
        TimeoutError: cryptohome wasn't mounted before timeout
    """
    wait_for_condition(
        condition=lambda: cryptohome.is_vault_mounted(user),
        timeout_msg='Timed out waiting for cryptohome to be mounted',
        timeout=timeout,
        process='cryptohomed',
        crash_msg='cryptohomed crashed during mount attempt')


def wait_for_ownership(timeout=constants.DEFAULT_OWNERSHIP_TIMEOUT):
    wait_for_condition(
        condition=lambda: os.access(constants.OWNER_KEY_FILE, os.F_OK),
        timeout_msg='Timed out waiting for ownership',
        timeout=timeout,
        process=constants.BROWSER,
        crash_msg='Chrome crashed before ownership could be taken.')
