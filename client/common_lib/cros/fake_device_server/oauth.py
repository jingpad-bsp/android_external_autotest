# Copyright 2015 The Chromium OS Authors. All rights reserved.
# Use of this source code is governed by a BSD-style license that can be
# found in the LICENSE file.


from cherrypy import tools

import common
import logging
from fake_device_server import common_util
from fake_device_server import server_errors

OAUTH_PATH = 'oauth'

TEST_API_KEY = 'this_is_an_api_key'
TEST_DEVICE_ACCESS_TOKEN = 'a_device_access_token'
TEST_DEVICE_REFRESH_TOKEN = 'a_device_refresh_token'
TOKEN_EXPIRATION_SECONDS = 24 * 60 * 60  # 24 hours.


class OAuth(object):
    """The bare minimum to make Buffet think its talking to OAuth."""

    # Needed for cherrypy to expose this to requests.
    exposed = True

    def __init__(self):
        self._device_access_token = TEST_DEVICE_ACCESS_TOKEN
        self._device_refresh_token = TEST_DEVICE_REFRESH_TOKEN


    def get_api_key_from_access_token(self, access_token):
        if access_token == self._device_access_token:
            return TEST_API_KEY
        return None


    def is_request_authorized(self):
        """Checks if the access token in an incoming request is correct."""
        access_token = common_util.get_access_token()
        if access_token == self._device_access_token:
            return True
        logging.info('Wrong access token - expected %s but device sent %s',
                     self._device_access_token, access_token)
        return False


    @tools.json_out()
    def POST(self, *args, **kwargs):
        """Handle a post to get a refresh/access token.

        We expect the device to provide:
            {"code", auth_code},
            {"client_id", client_id_},
            {"client_secret", client_secret_},
            {"redirect_uri", "oob"},
            {"scope", "https://www.googleapis.com/auth/clouddevices"},
            {"grant_type", "authorization_code"}

        but we're going to ignore all that and return hardcoded values.

        """
        path = list(args)
        if path == ['token']:
            response = {
                'access_token': self._device_access_token,
                'refresh_token': self._device_refresh_token,
                'expires_in': TOKEN_EXPIRATION_SECONDS,
            }
            return response
        elif path == ['invalidate_all_access_tokens']:
            # By concatenating '_X' to the end of existing access
            # token, this will effectively invalidate the access token
            # previously granted to a device and cause us to return
            # the concatenated one for future requests.
            self._device_access_token += '_X'
            return dict()
        else:
            raise server_errors.HTTPError(
                    400, 'Unsupported oauth path %s' % path)
