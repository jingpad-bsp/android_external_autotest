# Copyright (c) 2013 The Chromium OS Authors. All rights reserved.
# Use of this source code is governed by a BSD-style license that can be
# found in the LICENSE file.

import logging

from autotest_lib.client.common_lib import error
from autotest_lib.server import autotest
from autotest_lib.server import test


class sonic_AppTest(test.test):
    """Tests that a sonic device can start its apps."""
    version = 1


    def run_once(self, cros_host, sonic_host, app='ChromeCast', payload=None):
        """Sonic test to start an app.

        By default this test will test tab cast by installing an extension
        on the cros host and using chromedriver to cast a tab. If another app
        is specified, like YouTube or Netflix, the app is tested directly
        through the server running on port 8080 on the sonic device.

        @param app: The name of the application to start.
            eg: YouTube
        @param payload: The payload to send to the app.
            eg: http://www.youtube.com

        @raises CmdExecutionError: If a command failed to execute on the host.
        @raises TestError: If the app didn't start, or the app was unrecognized,
            or the payload is invalid.
        """
        sonic_host.run('logcat -c')

        if app == 'ChromeCast':
            sonic_host.enable_test_extension()
            client_at = autotest.Autotest(cros_host)
            client_at.run_test('desktopui_SonicExtension',
                               chromecast_ip=sonic_host.hostname)
        elif payload and (app == 'Netflix' or app == 'YouTube'):
            sonic_host.client.start_app(app, payload)
        else:
            raise error.TestError('Cannot start app %s with payload %s' %
                                  (app, payload))

        log = sonic_host.run('logcat -d').stdout
        app_started_confirmation = 'App started:'
        for line in log.split('\n'):
            if app_started_confirmation in line:
                logging.info('Successfully started app: %s', line)
                break
        else:
            logging.error(log)
            raise error.TestError('App %s failed to start' % app)


    def cleanup(self, cros_host, sonic_host, app='ChromeCast'):
        sonic_host.client.stop_app(app)

