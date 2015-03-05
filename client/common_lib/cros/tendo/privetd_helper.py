# Copyright 2014 The Chromium OS Authors. All rights reserved.
# Use of this source code is governed by a BSD-style license that can be
# found in the LICENSE file.

import json
import logging
import random
import string
import time

from autotest_lib.client.common_lib import error
from autotest_lib.client.common_lib import utils
from autotest_lib.client.common_lib.cros.network import iw_runner

URL_PING = 'ping'
URL_INFO = 'info'
URL_AUTH = 'v3/auth'
URL_PAIRING_CONFIRM = 'v3/pairing/confirm'
URL_PAIRING_START = 'v3/pairing/start'
URL_SETUP_START = 'v3/setup/start'
URL_SETUP_STATUS = 'v3/setup/status'

SETUP_START_RESPONSE_WIFI_SECTION = 'wifi'

BOOTSTRAP_CONFIG_DISABLED = 'off'
BOOTSTRAP_CONFIG_AUTOMATIC = 'automatic'
BOOTSTRAP_CONFIG_MANUAL = 'manual'

WIFI_BOOTSTRAP_STATE_DISABLED = 'disabled'
WIFI_BOOTSTRAP_STATE_WAITING = 'waiting'
WIFI_BOOTSTRAP_STATE_CONNECTING = 'connecting'
WIFI_BOOTSTRAP_STATE_MONITORING = 'monitoring'

PRIVETD_CONF_FILE_PATH = '/tmp/privetd.conf'
PRIVETD_TEMP_STATE_FILE = '/tmp/privetd.state'

DEFAULT_HTTP_PORT = 80
DEFAULT_HTTPS_PORT = 443

DEFAULT_DEVICE_CLASS = 'AB'  # = development board
DEFAULT_DEVICE_MODEL_ID = 'AAA'  # = unregistered

# Using an instance of object forces consumers to use a reference
# to this object.
INFER_WIFI_INTERFACES = object()

def privetd_is_installed(host=None):
    """Check if the privetd binary is installed.

    @param host: Host object if we're interested in a remote host.
    @return True iff privetd is installed in this system.

    """
    run = utils.run
    if host is not None:
        run = host.run
    result = run('if [ -f /usr/bin/privetd ]; then exit 0; fi; exit 1',
                 ignore_status=True)
    if result.exit_status == 0:
        return True
    return False


class PrivetdConfig(object):
    """An object that knows how to restart privetd in various configurations."""

    _num_names_generated = 0

    @staticmethod
    def naive_restart(host=None):
        """Restart privetd without modifying any settings.

        @param host: Host object if privetd is running on a remote host.

        """
        run = utils.run
        if host is not None:
            run = host.run
        run('stop privetd', ignore_status=True)
        run('start privetd')


    @staticmethod
    def build_unique_device_name():
        """@return a test-unique name for a Privet device."""
        RAND_CHARS = string.ascii_lowercase + string.digits
        NUM_RAND_CHARS = 4
        rand_token = ''.join([random.choice(RAND_CHARS)
                              for _ in range(NUM_RAND_CHARS)])
        name = 'CrOS Core %s_%2d' % (rand_token,
                                     PrivetdConfig._num_names_generated)
        PrivetdConfig._num_names_generated += 1
        logging.debug('Generated unique device name %s', name)
        return name


    def __init__(self,
                 wifi_bootstrap_mode=BOOTSTRAP_CONFIG_DISABLED,
                 gcd_bootstrap_mode=BOOTSTRAP_CONFIG_DISABLED,
                 monitor_timeout_seconds=120,
                 connect_timeout_seconds=60,
                 bootstrap_timeout_seconds=300,
                 log_verbosity=0,
                 state_file_path=PRIVETD_TEMP_STATE_FILE,
                 clean_state=True,
                 enable_ping=False,
                 http_port=DEFAULT_HTTP_PORT,
                 https_port=DEFAULT_HTTPS_PORT,
                 device_whitelist=None,
                 disable_pairing_security=False,
                 device_name=None,
                 device_class=DEFAULT_DEVICE_CLASS,
                 device_model_id=DEFAULT_DEVICE_MODEL_ID):
        """Construct a privetd configuration.

        @param wifi_bootstrap_mode: one of BOOTSTRAP_CONFIG_* above.
        @param gcd_bootstrap_mode: one of BOOTSTRAP_CONFIG_* above.
        @param monitor_timeout_seconds: int timeout for the WiFi bootstrapping
                state machine.
        @param connect_timeout_seconds: int timeout for the WiFi bootstrapping
                state machine.
        @param bootstrap_timeout_seconds: int timeout for the WiFi bootstrapping
                state machine.
        @param log_verbosity: int logging verbosity for privetd.
        @param state_file_path: string path to privetd state file.
        @param clean_state: bool True to clear state from the state file.
                |state_file_path| must not be None if this is True.
        @param log_verbosity: integer verbosity level of log messages.
        @param enable_ping: bool True if we should enable the ping URL
                on the privetd web server.
        @param http_port: integer port number for the privetd HTTP server.
        @param https_port: integer port number for the privetd HTTPS server.
        @param device_whitelist: list of string network interface names to
                consider exclusively for connectivity monitoring (e.g.
                ['eth0', 'wlan0']). Alternatively, pass INFER_WIFI_INTERFACES
                to cause a list of WiFi interfaces to be inferred at restart
                time.
        @param disable_pairing_security: bool True to disable pairing security
        @param device_name: string Device name.  A 'unique' device name
                will be generated if this is unspecified.
        @param device_class: string device class, a two character string.
        @param device_model_id: string device model ID, a 3 character string.

        """
        self.wifi_bootstrap_mode = wifi_bootstrap_mode
        self.gcd_bootstrap_mode = gcd_bootstrap_mode
        self.monitor_timeout_seconds = monitor_timeout_seconds
        self.connect_timeout_seconds = connect_timeout_seconds
        self.bootstrap_timeout_seconds = bootstrap_timeout_seconds
        self.log_verbosity = log_verbosity
        self.clean_state = clean_state
        self.state_file_path = state_file_path
        self.enable_ping = enable_ping
        self.http_port = http_port
        self.https_port = https_port
        self.device_whitelist = device_whitelist
        self.disable_pairing_security = disable_pairing_security
        self.device_name = (device_name or
                            PrivetdConfig.build_unique_device_name())
        self.device_class = device_class
        self.device_model_id = device_model_id


    def restart_with_config(self, host=None):
        """Restart privetd in this configuration.

        @param host: Host object if privetd is running on a remote host.

        """
        run = utils.run
        if host is not None:
            run = host.run
        run('stop privetd', ignore_status=True)
        if self.device_whitelist == INFER_WIFI_INTERFACES:
            iw_helper = iw_runner.IwRunner(remote_host=host)
            netdevs = iw_helper.list_interfaces(desired_if_type='managed')
            self.device_whitelist = [netdev.if_name for netdev in netdevs]
            if not self.device_whitelist:
                raise error.TestFail(
                        'No WiFi interfaces found to whitelist for privetd.')
        conf_dict = {
                'wifi_bootstrapping_mode': self.wifi_bootstrap_mode,
                'gcd_bootstrapping_mode': self.gcd_bootstrap_mode,
                'monitor_timeout_seconds': self.monitor_timeout_seconds,
                'connect_timeout_seconds': self.connect_timeout_seconds,
                'bootstrap_timeout_seconds': self.bootstrap_timeout_seconds,
                'device_class': self.device_class,
                'device_model_id': self.device_model_id,
                'device_name': self.device_name,
        }
        flag_list = []
        flag_list.append('PRIVETD_LOG_LEVEL=%d' % self.log_verbosity)
        flag_list.append('PRIVETD_HTTP_PORT=%d' % self.http_port)
        flag_list.append('PRIVETD_HTTPS_PORT=%d' % self.https_port)
        flag_list.append('PRIVETD_CONFIG_PATH=%s' % PRIVETD_CONF_FILE_PATH)
        if self.enable_ping:
            flag_list.append('PRIVETD_ENABLE_PING=true')
        if self.disable_pairing_security:
            flag_list.append('PRIVETD_DISABLE_SECURITY=true')
        if self.device_whitelist:
            flag_list.append('PRIVETD_DEVICE_WHITELIST=%s' %
                             ','.join(self.device_whitelist))
        if self.state_file_path:
            flag_list.append('PRIVETD_STATE_PATH=%s' % self.state_file_path)
        conf_lines = ['%s=%s' % pair for pair in conf_dict.iteritems()]
        # Go through this convoluted shell magic here because we need to create
        # this file on both remote and local hosts (see how run() is defined).
        run('cat <<EOF >%s\n%s\nEOF\n' % (PRIVETD_CONF_FILE_PATH,
                                          '\n'.join(conf_lines)))
        if self.clean_state:
            if not self.state_file_path:
                raise error.TestError('Cannot clean unknown state file path.')
            run('echo > %s' % self.state_file_path)
            run('chown privetd:privetd %s' % self.state_file_path)
        run('start privetd %s' % ' '.join(flag_list))


    def is_softap_ssid(self, ssid):
        """Check whether |ssid| could represent privetd with this config.

        @param ssid: string SSID of network.
        @return True iff this could be a network started by privetd configured
                with settings in |self|.

        """
        logging.debug('Checking whether softAP SSID "%s" '
                      'looks like a privet SSID', ssid)

        if len(ssid) > 31:
            logging.debug('SSID was too long')
            return False
        if ssid.find('.') < 0:
            logging.debug('Missing SSID separator')
            return False
        name, suffix = ssid.split('.', 1)
        if len(suffix) != 10:
            logging.debug('Suffix was %d characters, rather than 10.',
                          len(suffix))
            return False
        device_class = suffix[0:2]
        model_id = suffix[2:5]
        flags = suffix[5:7]
        version = suffix[7:10]
        if version != 'prv':
            logging.debug('Suffix should end with prv, not %s', suffix)
            return False
        if self.device_class is not None and device_class != self.device_class:
            logging.debug('Expected device_class=%s, but got %s',
                          self.device_class, device_class)
            return False
        if self.device_model_id and model_id != self.device_model_id:
            logging.debug('Expected model_id=%s, but got %s',
                          self.device_model_id, model_id)
            return False
        # TODO(wiley) Add flag support
        if not name.startswith(self.device_name):
            logging.debug('Expected SSID to start with "%s" but got "%s".',
                          self.device_name, name)
            return False
        return True


class PrivetdHelper(object):
    """Delegate class containing logic useful with privetd."""


    def __init__(self, host=None, hostname='localhost',
                 http_port=DEFAULT_HTTP_PORT, https_port=DEFAULT_HTTPS_PORT):
        """Construct a PrivetdHelper

        @param host: host object where we should run the HTTP requests from.
        @param hostname: string hostname of host to issue HTTP requests against.
        @param http_port: int HTTP port to use when making HTTP requests.
        @param https_port: int HTTPS port to use when making HTTPs requests.

        """
        self._host = None
        self._run = utils.run
        if host is not None:
            self._host = host
            self._run = host.run
        self._hostname = hostname
        self._http_port = http_port
        self._https_port = https_port


    def _build_privet_url(self, path_fragment, use_https=True):
        """Builds a request URL for privet.

        @param path_fragment: URL path fragment to be appended to /privet/ URL.
        @param use_https: set to False to use 'http' protocol instead of https.

        @return The full URL to be used for request.

        """
        protocol = 'http'
        port = self._http_port
        if use_https:
            protocol = 'https'
            port = self._https_port
        url = '%s://%s:%s/privet/%s' % (protocol, self._hostname, port,
                                        path_fragment)
        return url


    def _http_request(self, url, request_data=None, retry_count=0,
                      retry_delay=0.3, headers={},
                      timeout_seconds=10,
                      tolerate_failure=False):
        """Sends a GET/POST request to a web server at the given |url|.

        If the request fails due to error 111:Connection refused, try it again
        after |retry_delay| seconds and repeat this to a max |retry_count|.
        This is needed to make sure peerd has a chance to start up and start
        responding to HTTP requests.

        @param url: URL path to send the request to.
        @param request_data: json data to send in POST request.
                If None, a GET request is sent with no data.
        @param retry_count: max request retry count.
        @param retry_delay: retry_delay (in seconds) between retries.
        @param headers: optional dictionary of http request headers
        @param timeout_seconds: int number of seconds for curl to wait
                to complete the request.
        @param tolerate_failure: True iff we should allow curl failures.
        @return The string content of the page requested at url.

        """
        logging.debug('Requesting %s', url)
        args = []
        if request_data is not None:
            headers['Content-Type'] = 'application/json; charset=utf8'
            args.append('--data')
            args.append(request_data)
        for header in headers.iteritems():
            args.append('--header')
            args.append(': '.join(header))
        # TODO(wiley do cert checking
        args.append('--insecure')
        args.append('--max-time')
        args.append('%d' % timeout_seconds)
        # Write the HTTP code to stdout
        args.append('-w')
        args.append('%{http_code}')
        output_file = '/tmp/privetd_http_output'
        args.append('-o')
        args.append(output_file)
        while retry_count >= 0:
            result = self._run('curl %s' % url, args=args,
                               ignore_status=True)
            retry_count -= 1
            raw_response = ''
            success = result.exit_status == 0
            http_code = result.stdout or 'timeout'
            if success:
                raw_response = self._run('cat %s' % output_file).stdout
                logging.debug('Got raw response: %s', raw_response)
            if success and http_code == '200':
                return raw_response
            if retry_count < 0:
                if tolerate_failure:
                    return None
                raise error.TestFail('Failed requesting %s (code=%s)' %
                                     (url, http_code))
            logging.warn('Failed to connect to host. Retrying...')
            time.sleep(retry_delay)


    def send_privet_request(self, path_fragment, request_data=None,
                            auth_token='Privet anonymous',
                            tolerate_failure=False):
        """Sends a privet request over HTTPS.

        @param path_fragment: URL path fragment to be appended to /privet/ URL.
        @param request_data: json data to send in POST request.
                             If None, a GET request is sent with no data.
        @param auth_token: authorization token to be added as 'Authorization'
                           http header using 'Privet' as the auth realm.
        @param tolerate_failure: True iff we should allow curl failures.

        """
        if isinstance(request_data, dict):
                request_data = json.dumps(request_data)
        headers = {'Authorization': auth_token}
        url = self._build_privet_url(path_fragment, use_https=True)
        data = self._http_request(url, request_data=request_data,
                                  headers=headers,
                                  tolerate_failure=tolerate_failure)
        if data is None and tolerate_failure:
            return None
        try:
            json_data = json.loads(data)
            data = json.dumps(json_data)  # Drop newlines, pretty format.
        finally:
            logging.info('Received /privet/%s response: %s',
                         path_fragment, data)
        return json_data


    def ping_server(self, use_https=False):
        """Ping the privetd webserver.

        Reuses port numbers from the last restart request.  The server
        must have been restarted with enable_ping=True for this to work.

        @param use_https: set to True to use 'https' protocol instead of 'http'.

        """
        url = self._build_privet_url(URL_PING, use_https=use_https);
        content = self._http_request(url, retry_delay=5, retry_count=5)
        if content != 'Hello, world!':
            raise error.TestFail('Unexpected response from web server: %s.' %
                                 content)


    def privet_auth(self):
        """Go through pairing and insecure auth.

        @return resulting auth token.

        """
        data = {'pairing': 'pinCode', 'crypto': 'none'}
        pairing = self.send_privet_request(URL_PAIRING_START, request_data=data)

        data = {'sessionId': pairing['sessionId'],
                'clientCommitment': pairing['deviceCommitment']
        }
        self.send_privet_request(URL_PAIRING_CONFIRM, request_data=data)

        data = {'authCode': pairing['deviceCommitment'],
                'mode': 'pairing',
                'requestedScope': 'owner'
        }
        auth = self.send_privet_request(URL_AUTH, request_data=data)
        auth_token = '%s %s' % (auth['tokenType'], auth['accessToken'])
        return auth_token


    def setup_add_wifi_credentials(self, ssid, passphrase, data={}):
        """Add WiFi credentials to the data provided to setup_start().

        @param ssid: string ssid of network to connect to.
        @param passphrase: string passphrase for network.
        @param data: optional dict of information to append to.

        """
        data['wifi'] = {'ssid': ssid, 'passphrase': passphrase}
        return data


    def setup_start(self, data, auth_token):
        """Provide privetd with credentials for various services.

        @param data: dict of information to give to privetd.  Should be
                formed by one or more calls to setup_add_*() above.
        @param auth_token: string auth token returned from privet_auth()
                above.

        """
        # We don't return the response here, because in general, we may not
        # get one.  In many cases, we'll tear down the AP so quickly that
        # the webserver won't have time to respond.
        self.send_privet_request(URL_SETUP_START, request_data=data,
                                 auth_token=auth_token, tolerate_failure=True)


    def wifi_setup_was_successful(self, ssid, auth_token):
        """Detect whether privetd thinks bootstrapping has succeeded.

        @param ssid: string network we expect to connect to.
        @param auth_token: string auth token returned from prviet_auth()
                above.
        @return True iff setup/status reports success in connecting to
                the given network.

        """
        response = self.send_privet_request(URL_SETUP_STATUS,
                                            auth_token=auth_token)
        return (response['wifi']['status'] == 'success' and
                response['wifi']['ssid'] == ssid)
