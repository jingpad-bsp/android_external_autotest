# Copyright (c) 2010 The Chromium OS Authors. All rights reserved.
# Use of this source code is governed by a BSD-style license that can be
# found in the LICENSE file.

import logging, os, shutil
import common
import constants, httpd, login

from autotest_lib.client.bin import utils
from autotest_lib.client.common_lib import error

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


class ChromeSession(object):
    """
    A class to open a tab within the running browser process.
    """

    def __init__(self, args=''):
        self.start(args)


    def start(self, args=''):
        if not login.logged_in():
            raise login.UnexpectedCondition("Not logged in!")

        # Open a new browser tab in the running chrome process.
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

        # Assign the handlers.
        http_server.add_url_handler('/',
            lambda server, form, o=self: o.return_html(server, form))
        http_server.add_url_handler('/answer',
            lambda server, form, o=self: o.return_html(server, form))

        try:
            # Start a Chrome session to load the page.
            session = ChromeSession(url)
            latch = http_server.add_wait_url('/answer')
            latch.wait(self._timeout)
        finally:
            session.close()
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
