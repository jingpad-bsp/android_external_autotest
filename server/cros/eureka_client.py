# Copyright (c) 2013 The Chromium OS Authors. All rights reserved.
# Use of this source code is governed by a BSD-style license that can be
# found in the LICENSE file.

import httplib
import json
import logging
import socket
import time
import urllib2

import common

from autotest_lib.client.common_lib import error
from autotest_lib.client.common_lib.cros import retry

# Give all our rpcs about six seconds of retry time. If a longer timeout
# is desired one should retry from the caller, this timeout is only meant
# to avoid uncontrolled circumstances like network flake, not, say, retry
# right across a reboot.
BASE_REQUEST_TIMEOUT = 0.1
JSON_HEADERS = {'Content-Type': 'application/json'}
RPC_EXCEPTIONS = (httplib.BadStatusLine, socket.error, urllib2.HTTPError)


@retry.retry(RPC_EXCEPTIONS, timeout_min=BASE_REQUEST_TIMEOUT)
def _get(url):
    """Get request to the give url.

    @raises: Any of the retry exceptions, if we hit the timeout.
    @raises: error.TimeoutException, if the call itself times out.
        eg: a hanging urlopen will get killed with a TimeoutException while
        multiple retries that hit different Http errors will raise the last
        HttpError instead of the TimeoutException.
    """
    return urllib2.urlopen(url).read()


@retry.retry(RPC_EXCEPTIONS, timeout_min=BASE_REQUEST_TIMEOUT)
def _post(url, data):
    """Post data to the given url.

    @param data: Json data to post.

    @raises: Any of the retry exceptions, if we hit the timeout.
    @raises: error.TimeoutException, if the call itself times out.
        For examples see docstring for _get method.
    """
    request = urllib2.Request(url, json.dumps(data),
                              headers=JSON_HEADERS)
    urllib2.urlopen(request)


class EurekaProxyException(Exception):
    """Generic exception raised when a eureka rpc fails."""
    pass


class EurekaProxy(object):
    """Client capable of making calls to the eureka device server."""
    POLLING_INTERVAL = 5
    SETUP_SERVER_PORT = '8008'
    EUREKA_SETUP_SERVER = 'http://%s:%s/setup'

    def __init__(self, hostname):
        """
        @param host: The host object representing the Eureka device.
        """
        self._eureka_setup_server = (self.EUREKA_SETUP_SERVER %
                                     (hostname, self.SETUP_SERVER_PORT))


    def get_info(self):
        """Returns information about the eureka device.

        @return: A dictionary containing information about the eureka device.
        """
        eureka_info_url = '%s/%s' % (self._eureka_setup_server, 'eureka_info')
        try:
            return json.loads(_get(eureka_info_url))
        except (RPC_EXCEPTIONS, error.TimeoutException) as e:
            raise EurekaProxyException('Could not retrieve information about '
                                       'eureka device: %s' % e)


    def get_build_number(self, timeout_mins=0.1):
        """
        Returns the build number of the build on the device.

        @param timeout_mins: Timeout in minutes. By default this should
            return almost immediately and hence has a timeout of 6 seconds.
            If we're rebooting, and would like the boot id of the build after
            the reboot is complete this timeout should be in O(minutes).

        @raises EurekaProxyException: If unable to get build number within the
            timeout specified.
        """
        current_time = int(time.time())
        end_time = current_time + timeout_mins*60

        while end_time > current_time:
            try:
                eureka_info = self.get_info()
            except EurekaProxyException:
                pass
            else:
                return eureka_info.get('build_version', None)
            time.sleep(self.POLLING_INTERVAL)
            current_time = int(time.time())

        raise EurekaProxyException('Timed out trying to get build number.')


    def reboot(self, when="now"):
        """
        Post to the server asking for a reboot.

        @param when: The time till reboot. Can be any of:
            now: immediately
            fdr: set factory data reset flag and reboot now
            ota: set recovery flag and reboot now
            ota fdr: set both recovery and fdr flags, and reboot now
            ota foreground: reboot and start force update page
            idle: reboot only when idle screen usage > 10 mins

        @raises EurekaProxyException: if we're unable to post a reboot request.
        """
        reboot_url = '%s/%s' % (self._eureka_setup_server, 'reboot')
        reboot_params = {"params": when}
        logging.info('Rebooting device through %s.', reboot_url)
        try:
            _post(reboot_url, reboot_params)
        except (RPC_EXCEPTIONS, error.TimeoutException) as e:
            raise EurekaProxyException('Could not reboot eureka device through '
                                       '%s: %s' % (self.SETUP_SERVER_PORT, e))
