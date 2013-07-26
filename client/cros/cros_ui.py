# Copyright (c) 2012 The Chromium OS Authors. All rights reserved.
# Use of this source code is governed by a BSD-style license that can be
# found in the LICENSE file.

import common, logging, os, time

from autotest_lib.client.bin import utils
from autotest_lib.client.common_lib import error
from autotest_lib.client.cros import constants, httpd

# Log messages used to signal when we're restarting UI. Used to detect
# crashes by cros_ui_test.UITest.
UI_RESTART_ATTEMPT_MSG = 'cros_ui.py: Attempting StopSession...'
UI_RESTART_COMPLETE_MSG = 'cros_ui.py: StopSession complete.'
DEFAULT_TIMEOUT = 90  # longer because we may be crash dumping now.

def xcommand(cmd):
    """
    Add the necessary X setup to a shell command that needs to connect to the X
    server.

    @param cmd: the command line string
    @return a modified command line string with necessary X setup
    """
    return 'DISPLAY=:0 XAUTHORITY=/home/chronos/.Xauthority ' + cmd


def xcommand_as(cmd, user='chronos'):
    """
    Same as xcommand, except wrapped in a su to the desired user.
    """
    return xcommand('su %s -c \'%s\'' % (user, cmd))


def xsystem(cmd, timeout=None, ignore_status=False):
    """
    Run the command cmd, using utils.system, after adding the necessary
    setup to connect to the X server.
    """

    return utils.system(xcommand(cmd), timeout=timeout,
                        ignore_status=ignore_status)


def xsystem_as(cmd, user='chronos', timeout=None, ignore_status=False):
    """
    Run the command cmd as the given user, using utils.system, after adding
    the necessary setup to connect to the X server.
    """

    return utils.system(xcommand_as(cmd, user=user), timeout=timeout,
                        ignore_status=ignore_status)


def get_autox():
    """Return a new autox instance."""
    # we're running as root, but need to connect to chronos' X session
    xauth_filename = '/home/chronos/.Xauthority'
    os.environ.setdefault('XAUTHORITY', xauth_filename)
    os.environ.setdefault('DISPLAY', ':0.0')

    # autox (python-xlib, actually) will throw an XauthError exception if it
    # tries to connect to the X server before the .Xauthority file has been
    # created; see http://crosbug.com/12389.
    utils.poll_for_condition(
        lambda: os.path.exists(xauth_filename),
        utils.TimeoutError('Timed out waiting for %s.' % xauth_filename))

    import autox
    return autox.AutoX()


def _clear_login_prompt_state():
    """Clear the magic file indicating that the login prompt is ready."""
    if os.access(constants.LOGIN_PROMPT_VISIBLE_MAGIC_FILE, os.F_OK):
        os.unlink(constants.LOGIN_PROMPT_VISIBLE_MAGIC_FILE)


def _wait_for_login_prompt(timeout=DEFAULT_TIMEOUT):
    """Wait until the login prompt is on screen and ready.

    When the login prompt appears, the session manager will log this via
    bootstat, creating a magic file in /tmp. We can check whether the prompt
    has appeared yet using the following pattern:

       _clear_login_prompt_state()
       logout()
       _wait_for_login_prompt()

    TODO(davidjames): Reimplement this function using dbus messages so we
                      don't depend on magic files.

    Args:
        timeout: float number of seconds to wait

    Raises:
        TimeoutError: Login prompt didn't get up before timeout
    """

    utils.poll_for_condition(
        condition=lambda: os.access(
            constants.LOGIN_PROMPT_VISIBLE_MAGIC_FILE, os.F_OK),
        exception=utils.TimeoutError('Timed out waiting for login prompt'),
        timeout=timeout)


def stop_and_wait_for_chrome_to_exit(timeout_secs=40):
    """Stops the UI and waits for chrome to exit.

    Stops the UI and waits for all chrome processes to exit or until
    timeout_secs is reached.

    Args:
        timeout_secs: float number of seconds to wait.

    Returns:
        True upon successfully stopping the UI and all chrome processes exiting.
        False otherwise.
    """
    status = utils.system("stop ui", ignore_status=True)
    if status:
        logging.error('stop ui returned non-zero status: %s', status)
        return False
    start_time = time.time()
    while time.time() - start_time < timeout_secs:
        status = utils.system('pgrep chrome', ignore_status=True)
        if status == 1: return True
        time.sleep(1)
    logging.error('stop ui failed to stop chrome within %s seconds',
                  timeout_secs)
    return False


def stop(allow_fail=False):
    return utils.system("stop ui", ignore_status=allow_fail)


def start(allow_fail=False, wait_for_login_prompt=True):
    """Start the login manager and wait for the prompt to show up."""
    _clear_login_prompt_state()
    result = utils.system("start ui", ignore_status=allow_fail)
    # If allow_fail is set, the caller might be calling us when the UI job
    # is already running. In that case, the above command fails.
    if result == 0 and wait_for_login_prompt:
        _wait_for_login_prompt()
    return result


def restart(impl=None):
    """Restart the session manager.

    - If the user is logged in, the session will be terminated.
    - To ensure all processes are up and ready, this function will wait
      for the login prompt to show up and be marked as visible.

    Args:
        impl: Method to use to restart the session manager. By
              default, the session manager is restarted using upstart.
    """

    _clear_login_prompt_state()

    # Log what we're about to do to /var/log/messages. Used to log crashes later
    # in cleanup by cros_ui_test.UITest.
    utils.system('logger "%s"' % UI_RESTART_ATTEMPT_MSG)

    try:
        if impl is not None:
            impl()
        elif utils.system('restart ui', ignore_status=True) != 0:
            raise error.TestError('Could not stop session')

        # Wait for login prompt to appear to indicate that all processes are
        # up and running again.
        _wait_for_login_prompt()
    finally:
        utils.system('logger "%s"' % UI_RESTART_COMPLETE_MSG)


def nuke():
    """Nuke the login manager, waiting for it to restart."""
    restart(lambda: utils.nuke_process_by_name('session_manager'))


class ChromeSession(object):
    """
    A class to open a tab within the running browser process.
    """

    def __init__(self, args=''):
        self.start(args)


    def start(self, args=''):

        cmd = '%s --no-first-run --user-data-dir=%s %s' % (
            constants.BROWSER_EXE, constants.USER_DATA_DIR, args)
        xsystem_as(cmd)


_HTML_HEADER_ = '''
<html><head>
<title>Question Dialog</title>
<script language="Javascript">
function do_submit(value) {
    document.forms[0].result.value = value;
    document.forms[0].submit();
}
</script>
</head><body>
<h3>%s</h3>
<form action="/answer" method="post">
    <input type="hidden" name="result" value="">
'''

_HTML_BUTTON_ = '''<input type="button" value="%s" onclick="do_submit('%s')">'''
_HTML_CHECKBOX_ = '''<input type="checkbox" name="%s">%s'''
_HTML_TEXT_ = '''%s <input type="text" name="%s">'''

_HTML_FOOTER_ = '''</form></body></html>'''


def add_html_elements(template, values):
    if not values:
        return ''
    html_elements = ['<table><tr>']
    for value in values:
        html_elements.append('<td>' + template % (value, value))
    html_elements.append('</table><p>')
    return ' '.join(html_elements)


class Dialog(object):
    """
    A class to create a simple interaction with a user, like asking a question
    and receiving the answer.
    """

    def __init__(self, question='',
                 choices=['Pass', 'Fail'],
                 checkboxes=[],
                 textinputs=[],
                 timeout=60):
        self.init(question, choices, checkboxes, textinputs, timeout)


    def init(self, question='',
             choices=['Pass', 'Fail'],
             checkboxes=[],
             textinputs=[],
             timeout=60):
        self._question = question
        self._choices = choices
        self._checkboxes = checkboxes
        self._textinputs = textinputs
        self._timeout = timeout


    def return_html(self, server, args):
        html = _HTML_HEADER_ % self._question
        html += add_html_elements(_HTML_CHECKBOX_, self._checkboxes)
        html += add_html_elements(_HTML_TEXT_, self._textinputs)
        html += add_html_elements(_HTML_BUTTON_, self._choices)
        html += _HTML_FOOTER_
        server.wfile.write(html)


    def get_entries(self):
        # Run a HTTP server.
        base_port = 8000
        while base_port < 9000:
            url = 'http://localhost:%d/' % base_port
            try:
                http_server = httpd.HTTPListener(base_port)
                break
            except httpd.socket.error:
                # The socket must be still bound since last time.
                base_port = base_port + 1
                continue
        else:
            # This is unlikely to happen, but just in case.
            raise error.TestError('Failed to start HTTP server.')

        http_server.run()

        try:
            # Assign the handlers.
            http_server.add_url_handler('/',
                lambda server, form, o=self: o.return_html(server, form))
            http_server.add_url_handler('/answer',
                lambda server, form, o=self: o.return_html(server, form))

            # Start a Chrome session to load the page.
            session = ChromeSession(url)
            latch = http_server.add_wait_url('/answer')
            latch.wait(self._timeout)
        finally:
            http_server.stop()

        # Return None if timeout.
        if not latch.is_set():
            http_server.stop()
            return None

        entries = http_server.get_form_entries()
        http_server.stop()
        return entries


    def get_result(self):
        entries = self.get_entries()
        if not entries:
            return None
        return entries.get('result')
