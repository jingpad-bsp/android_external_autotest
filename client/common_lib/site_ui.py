# Copyright (c) 2010 The Chromium OS Authors. All rights reserved.
# Use of this source code is governed by a BSD-style license that can be
# found in the LICENSE file.

import logging, shutil
from autotest_lib.client.common_lib import site_httpd, utils


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


class ChromeSession(object):
    """
    A class to start and close Chrome sessions.
    """

    def __init__(self, args='', clean_state=True, suid=True):
        self._clean_state = clean_state
        self.start(args, suid=suid)


    def __del__(self):
        self.close()


    def start(self, args='', suid=True):
        if self._clean_state:
            # Delete previous browser state if any
            shutil.rmtree('/home/chronos/.config/chromium', ignore_errors=True)

        # Open a new browser window as a background job
        cmd = '/opt/google/chrome/chrome --no-first-run ' + args
        cmd = xcommand(cmd)
        if suid:
            cmd = 'su chronos -c \'%s\'' % cmd
        self.job = utils.BgJob(cmd)


    def close(self):
        if self.job is not None:
            utils.nuke_subprocess(self.job.sp)
        self.job = None



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

_HTML_FOOTER_ = '''</form></body></html>'''



class Dialog(object):
    """
    A class to create a simple interaction with a user, like asking a question
    and receiving the answer.
    """

    def __init__(self, question='', choices=['Pass', 'Fail'], timeout=60):
        self.init(question, choices, timeout)


    def init(self, question='', choices=['Pass', 'Fail'], timeout=60):
        self._question = question
        self._choices = choices
        self._timeout = timeout


    def return_html(self, server, args):
        html = _HTML_HEADER_ % self._question
        for choice in self._choices:
            html += _HTML_BUTTON_ % (choice, choice)
        html += _HTML_FOOTER_
        server.wfile.write(html)


    def get_result(self):
        # Run a HTTP server.
        url = 'http://localhost:8000/'
        http_server = site_httpd.HTTPListener(8000)
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

        result = http_server.get_form_entries()['result']
        http_server.stop()
        return result
