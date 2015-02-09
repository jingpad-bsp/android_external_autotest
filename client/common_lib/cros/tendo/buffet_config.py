# Copyright 2015 The Chromium OS Authors. All rights reserved.
# Use of this source code is governed by a BSD-style license that can be
# found in the LICENSE file.

import dbus
import time

from autotest_lib.client.common_lib import error
from autotest_lib.client.common_lib import utils
from autotest_lib.client.common_lib.cros import dbus_send
from autotest_lib.client.common_lib.cros.fake_device_server import fake_oauth
from autotest_lib.client.common_lib.cros.fake_device_server import server

BUFFET_CONFIG_PATH = '/tmp/buffet.fake.conf'
BUFFET_STATE_PATH = '/tmp/buffet.fake.state'

SERVICE_NAME = 'org.chromium.Buffet'

MANAGER_INTERFACE = 'org.chromium.Buffet.Manager'
MANAGER_OBJECT_PATH = '/org/chromium/Buffet/Manager'

TEST_MESSAGE = 'Hello world!'

LOCAL_SERVER_PORT = server.PORT
LOCAL_OAUTH_URL = 'http://localhost:%d/%s/' % (LOCAL_SERVER_PORT,
                                               fake_oauth.OAUTH_PATH)
LOCAL_SERVICE_URL = 'http://localhost:%d/' % LOCAL_SERVER_PORT
TEST_API_KEY = 'this_is_an_api_key'

LOCAL_CLOUD_FAKES = {
        'client_id': 'this_is_my_client_id',
        'client_secret': 'this_is_my_client_secret',
        'api_key': TEST_API_KEY,
        'oauth_url': LOCAL_OAUTH_URL,
        'service_url': LOCAL_SERVICE_URL,
}


class BuffetConfig(object):
    """An object that knows how to restart buffet in various configurations."""

    @staticmethod
    def naive_restart(host=None):
        """Restart Buffet without configuring it in any way.

        @param host: Host object if we're interested in a remote host.

        """
        run = utils.run if host is None else host.run
        run('stop buffet', ignore_status=True)
        run('start buffet')


    def __init__(self,
                 log_verbosity=None,
                 clean_state=True,
                 use_local_cloud_fakes=True):
        self.log_verbosity = log_verbosity
        self.clean_state = clean_state
        self.use_local_cloud_fakes = use_local_cloud_fakes


    def restart_with_config(self, host=None, timeout_seconds=10):
        """Restart Buffet with this configuration.

        @param host: Host object if we're interested in a remote host.
        @param timeout_seconds: number of seconds to wait for Buffet to
                come up.

        """
        run = utils.run if host is None else host.run
        run('stop buffet', ignore_status=True)
        flag_list = []
        if self.log_verbosity:
            flag_list.append('BUFFET_LOG_LEVEL=%d' % self.log_verbosity)
        if self.use_local_cloud_fakes:
            conf_lines = ['%s=%s' % pair
                          for pair in LOCAL_CLOUD_FAKES.iteritems()]
            # Go through this convoluted shell magic here because we need to
            # create this file on both remote and local hosts (see how run() is
            # defined).
            run('cat <<EOF >%s\n%s\nEOF\n' %
                (BUFFET_CONFIG_PATH, '\n'.join(conf_lines)))
            flag_list.append('BUFFET_CONFIG_PATH=%s' % BUFFET_CONFIG_PATH)
        if self.clean_state:
            run('echo > %s' % BUFFET_STATE_PATH)
            run('chown buffet:buffet %s' % BUFFET_STATE_PATH)
            flag_list.append('BUFFET_STATE_PATH=%s' % BUFFET_STATE_PATH)
        run('start buffet %s' % ' '.join(flag_list))
        start_time = time.time()
        while time.time() - start_time < timeout_seconds:
            result = dbus_send.dbus_send(
                    SERVICE_NAME, MANAGER_INTERFACE, MANAGER_OBJECT_PATH,
                    'TestMethod', args=[dbus.String(TEST_MESSAGE)],
                    host=host, tolerate_failures=True)
            if result and result.response == TEST_MESSAGE:
                return
            time.sleep(0.5)

        raise error.TestFail('Buffet failed to restart in time.')
