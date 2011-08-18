# Copyright (c) 2011 The Chromium OS Authors. All rights reserved.
# Use of this source code is governed by a BSD-style license that can be
# found in the LICENSE file.

import logging, re
from autotest_lib.client.common_lib import error, pexpect, pxssh
from autotest_lib.server import hosts
from autotest_lib.server import utils

class CiscoRunResult(object):
    """
    Dummy result object returned in response to a ".run()" command
    """
    def __init__(self, stdout='', stderr=''):
        self.stdout = stdout
        self.stderr = stderr

class CiscoHostProxy(object):
    """
    Cisco host proxy.  Accepts command as if it were an SSH host
    """

    def __init__(self, proxy_addr, router_addr):
        self.proxy_addr = proxy_addr
        self.router_addr = router_addr
        self.proxy = hosts.SSHHost(proxy_addr)
        self.ip = router_addr

    def run(self, call, **dargs):
        """
        TODO(pstew): Return dummy result for now.  We can remove this when
        we're sure there aren't any residual bits of code trying to run
        Linux shell commands directly on a site_*_router.
        """
        return CiscoRunResult()

    def start(self):
        """
        Open up an SSH tunnel through our proxy to the Cisco, then open
        an SSH command shell on the Cisco through this tunnel.
        """
        port = 20000
        tries = 10
        while tries > 0:
            cmdline = ('ssh -f -L %d:%s:22 '
                       '-o ExitOnForwardFailure=yes '
                       '-o StrictHostKeyChecking=no '
                       '-o UserKnownHostsFile=/dev/null '
                       '-o ServerAliveInterval=60 '
                       '-o ConnectTimeout=10 -l root %s sleep 1d' %
                       (port, self.router_addr, self.proxy_addr))
            result = utils.run(cmdline, 10, True,
                               utils.TEE_TO_LOGS, utils.TEE_TO_LOGS,
                               verbose=False, stdin=None,
                               stderr_is_expected=True)
            if 'Address already in use' in result.stderr:
                tries -= 1
                port += 1
            elif result.exit_status > 0:
                logging.info("command execution error: %s" % result.stderr)
                raise error.TestFail("command execution error: %s" %
                                     result.stderr.rstrip('\n'))
            else:
                break
        else:
            raise error.TestFail("Could not allocate port for Cisco proxy")
        logging.info("Cisco SSH proxy started on port %d" % port)

        self.cisco = pxssh.pxssh()
        self.cisco.login('127.0.0.1', 'Cisco', 'Cisco', port=port,
                         original_prompt='ap[>#]', auto_prompt_reset=False)
        self.cisco.PROMPT = 'ap(\(.*\))?[>#]'
        self.cisco.TIMEOUT = 2
        self.cisco.sendline('enable')
        self.cisco.expect('Password:')
        self.cisco.sendline('Cisco')
        self.cisco.prompt()
        self.cmd('terminal length 0')
        self.reset()

    def reset(self):
        """
        Reset the AP back to default.  Although we use the "configure
        memory" command to reload the configuration from non-volatile
        RAM, not everything gets cleared unless you do a lengthy
        reboot, or cheat a little by clearing known bits of state.
        """
        self.cmd('configure memory', timeout=10)
        # Argh.  Despite "reloading" from memory, SSIDs are still not purged!
        self.remove_ssids()

    def remove_ssids(self):
        """
        We use the "show dot11 bssid" command to list ssids, and clear
        them individually.  The response is of the form:

        Interface      BSSID         Guest  SSID
        Dot11Radio0   b8be.bf45.61b0  Yes  Check11g_cisco_192_168_2_1ch1

        and we take the Interface and SSID parameters to form a config
        script to remove these entries.
        """
        deconfigs = {}
        for line in self.cmd('show dot11 bssid').splitlines():
            cols = re.split('\s+', line)
            if len(cols) >= 4 and cols[0] != 'Interface':
                # TODO(pstew): Cisco is shady about whitespace in SSIDs!
                ssid = ' '.join(cols[3:])
                key = 'interface %s' % cols[0]
                if key not in deconfigs:
                    deconfigs[key] = {}
                deconfigs[key]['ssid %s' % ssid] = None
        self.configure(deconfigs)

    def cmd(self, cmd, **dargs):
        """
        Send a command to the Cisco and wait for a response (and new prompt).
        The output response is returned.
        """
        # TODO(pstew): This is a little noisy but useful in early days
        logging.info('cisco command: %s' % cmd)
        self.cisco.sendline(cmd)
        self.cisco.prompt(**dargs)
        response = self.cisco.before.rstrip('\n')
        if '% ' in response:
            raise error.TestFail('Cisco router error for command "%s":\n\t%s' %
                                 (cmd, response))
        if response.startswith(cmd):
            response = response[len(cmd):].strip('\n')
        logging.info('cisco response: %s' % response)
        return response

    def configpriority(self, item):
        """
        Some configuration options need to come before/after others.  The
        priority order is currently:
           0: "shutdown"
           1: "no ssid ..."
           2: encryption mode, authentication
           3: authentication key-management
           4: Everything else
           5: Keys marked as "*delete-last*"
           6: "no shutdown" (enable)
        """
        if item[0].startswith('ssid') and not item[1]:
            return 1
        if item[0] in ('encryption mode', 'authentication'):
            return 2
        if item[0] == 'authentication key-management':
            return 3
        if item[0] == 'shutdown':
            return 0 if item[1] else 6
        if item[1] == '*delete-last*':
            return 5
        return 4

    def config_item(self, var, val):
        """
        Set an individual parameter on the Cisco.  The device should
        already be in "configuration" mode.  This sets a variable 'var'
        to a value 'val'.  There are a number of special cases, notably:

          * If 'val' is a dict, it is assumed that the 'var' parameter
            is a standalone command that will enter the Cisco into an
            additional lower command level that we'll need to exit later.
            Each recursive pair in the dict should be applied at this level.
            Parameters from the dict are sorted in a priority order.
          * If 'val' is None, we need to disable this parameter, using the
            'no' prefix.
          * If 'val' is True, this command should be sent by itself.
          * Otherwise, the command sent is 'var val'
        """
        if val.__class__ == dict:
            if var:
                self.cmd(var)
            for ivar, ival in sorted(val.iteritems(), key=self.configpriority):
                self.config_item(ivar, ival)
            self.cmd('exit')
        elif val == None or val == '*delete-last*':
            self.cmd('no %s' % var)
        elif val == True:
            self.cmd(var)
        else:
            self.cmd('%s %s' % (var, val))

    def configure(self, config):
        """
        Take a configuration dictionary and send it to the Cisco
        """
        if not config:
            return
        logging.info('cisco configure: %s' % repr(config))
        self.cmd('configure terminal')
        self.config_item(None, config)

    def stop(self):
        """
        End the SSH tunnel by killing the impossibly long sleep command
        running on the server.
        """
        self.proxy.run('pkill -f "sleep 1d"', ignore_status=True)

class CiscoRouter(object):
    """
    Cisco Aironet WiFi Router support for WiFiTest class.

    This class implements test methods/steps that communicate with a
    Cisco AP sitting behind a Linux system.  The router must be
    pre-configured to DHCP using the hostname "cisco" so it can be
    properly identified above in "discoverCiscoRouter".  We will then
    create an ssh tunnel on the linux system for use in access to the
    rroute.
    """


    def __init__(self, server, params, defssid, address):
        self.defssid = defssid
        self.address = address
        self.proxy = CiscoHostProxy(server, address)
        self.proxy.start()

        # Discover which frequencies each interface is in charge of
        re_radio_name = re.compile('(\w+)')
        re_radio_freq = re.compile('Hardware is .* ([0-9.]*)GHz Radio')
        radio_name = None
        self.phydev2 = None
        self.phydev5 = None
        for line in self.proxy.cmd('show interfaces').splitlines():
            match_name = re_radio_name.match(line)
            match_freq = re_radio_freq.search(line)
            if match_name:
                radio_name = match_name.group(1)
            elif match_freq:
                freq = match_freq.group(1)
                if freq == '2.4':
                    self.phydev2 = radio_name
                elif freq == '5':
                    self.phydev5 = radio_name
                else:
                    logging.info("Unmatched frequency %s for radio %s" %
                                 (freq, radio_name))

        self.ap = {
            'config': {},
            'status': {}
        }

        # Compile a set of rate parameters to pass to the Cisco
        self.rates = {}
        self.rates['11b'] = ['basic-1.0', 'basic-2.0', 'basic-5.5',
                             'basic-11.0']
        self.rates['11a'] =  ['basic-6.0', '9.0', '12.0', '18.0', '24.0',
                              '36.0', '48.0', '54.0']
        self.rates['11g'] = self.rates['11b'] + self.rates['11a']
        self.rates['pureg'] = self.rates['11a']
        self.rates['n-only'] = ['m0.', 'm1.', 'm2.', 'm3.', 'm4.', 'm5.',
                                'm6.', 'm7.', 'm8.', 'm9.', 'm10.', 'm11.',
                                'm12.', ' m13.', 'm14.', 'm15.']
        # TODO(pstew): Cisco barfs if all the basic rates are omitted
        self.rates['puren'] = ['basic-54.0'] + self.rates['n-only']
        self.rates['11n'] = self.rates['11g'] + self.rates['n-only']

    def create(self, params):
        """ Create a wifi device of the specified type """
        self.apmode = params['type'] in ("ap", "hostap")
        if not self.apmode:
            raise error.TestFail("Cisco router currently only supports AP mode")

    def get_proxy(self):
        return self.proxy

    def has_local_server(self):
        return False

    def destroy(self, params):
        """ Destroy a previously created configuration """
        self.deconfig({})
        self.proxy.reset()
        self.ap['config'] = {}

    def cleanup(self, params):
        """ Clean up any resources in use """
        self.proxy.stop()

    def deconfig(self, params):
        """ De-configure the AP (undo everything the configure did) """
        for interface, config in self.ap['status'].iteritems():
            newconfig = {}
            for key in config.keys():
                if (key.startswith('encryption key') and
                    'transmit-key' in config[key]):
                    # Cisco bug # CSCse30750 : Must delete transmit key last
                    newconfig[key] = '*delete-last*'
                elif key not in ('channel'):
                    newconfig[key] = None
            newconfig['shutdown'] = True
            self.proxy.configure({ 'interface %s' % interface: newconfig })
        self.ap['status'] = {}

    def config(self, params):
        """ Configure the AP per test requirements """
        multi_interface = 'multi_interface' in params
        if multi_interface:
            params.pop('multi_interface')

        config = self.ap['config']
        config.update(params)

        # Construct the skeleton interface configuration
        interface = self.phydev2
        ssid = self.ap.get('ssid', self.defssid)

        interface_conf = {
            'beacon period': None,
            'beacon dtim-period': None,
            'encryption mode': None,
            'speed': 'default',
            'channel width': None,
            'shutdown': None
        }
        ssid_conf = {
            'guest-mode': True,
            'authentication': 'open'
        }

        country_params = {
            'code': None,
            'dot11_d_mode': 'legacy',
            'indoor_mode': 'indoor'
        }
        for k, v in config.iteritems():
            if k == 'ssid':
                ssid = v
            elif k == 'ssid_suffix':
                ssid = self.defssid + v
            elif k == 'channel':
                freq = int(v)
                interface_conf['channel'] = freq

                # 2.4GHz
                if freq <= 2484:
                    # Freq = 5 * chan + 2407, except channel 14
                    interface = self.phydev2
                # 5GHz
                else:
                    interface = self.phydev5
            elif k in ('country', 'dotd', '-dotd'):
                if k == 'country':
                    country_params['code'] = v
                elif k == 'dotd':
                    country_params['dot11_d_mode'] = 'dot11d'
                elif k == '-dotd':
                    country_params['dot11_d_mode'] = 'legacy'
                if country_params['code']:
                    interface_conf['world-mode'] = ('%(dot11_d_mode)s '
                                                    'country-code %(code)s '
                                                    '%(indoor_mode)s' %
                                                    country_params)
                else:
                    interface_conf['world-mode'] = None
            elif k == 'mode':
                if 'pureg' in config:
                    interface_conf['speed'] = ' '.join(self.rates['pureg'])
                    interface_conf['speed only-ofdm'] = True
                elif 'puren' not in config:
                    interface_conf['speed'] = ' '.join(self.rates[v])
            elif k == 'puren':
                interface_conf['speed'] = ' '.join(self.rates['puren'])
            elif k == 'bintval':
                interface_conf['beacon period'] = v
            elif k == 'dtimperiod':
                interface_conf['beacon dtim-period'] = v
            elif k == 'rtsthreshold':
                interface_conf['rts threshold'] = v
            elif k == 'fragthreshold':
                interface_conf['fragment-threshold'] = v
            elif k == 'shortpreamble':
                interface_conf['preamble-short'] = True
            elif k == 'authmode':
                if v == "open":
                    ssid_conf['authentication'] = 'open'
                elif v == "shared":
                    ssid_conf['authentication'] = 'shared'
            elif k == 'hidessid':
                ssid_conf['guest-mode'] = None
            elif k == 'wme':
                interface_conf['dot11 qos mode'] = 'wmm'
            elif k == '-wme':
                interface_conf['dot11 qos mode'] = None
            elif k == 'security':
                if v == 'wep':
                    interface_conf['encryption mode'] = 'wep mandatory'
            elif k.startswith('wep_key'):
                keyno = int(k[7])
                if keyno == int(config.get('deftxkey', -1)):
                    txkey = ' transmit-key'
                else:
                    txkey = ''
                bits = len(v) * 4
                if bits == 104:
                    # Lies and inconsistencies -- Cisco counts the IV for 104bit
                    bits = 128
                interface_conf['encryption key %d' % (keyno+1)] = (
                    'size %dbit 0 %s%s' % (bits, v, txkey))
            elif k == 'deftxkey':
                if not ('wep_key%s' % v) in config:
                    raise error.TestFail("No WEP key specified for %d" % keyno)
            elif k == 'wepmode' and v == 'on':
                interface_conf['encryption mode'] = 'wep mandatory'
            elif k == 'wpa':
                if v == '1':
                    ssid_conf['authentication key-management'] = 'wpa version 1'
                elif v == '2':
                    ssid_conf['authentication key-management'] = 'wpa version 2'
                elif v == '3':
                    ssid_conf['authentication key-management'] = 'wpa'
            elif k == 'wpa_key_mgmt':
                if v == 'WPA-EAP':
                    raise error.TestFail("EAP not supported on Cisco yet")
            elif k in ('rsn_pairwise', 'wpa_pairwise'):
                types = list(set(config.get('rsn_pairwise', '').split(' ')) |
                             set(config.get('wpa_pairwise', '').split(' ')))
                cisco_types = []
                if 'TKIP' in types:
                    cisco_types.append('tkip')
                if 'CCMP' in types:
                    if config.get('wpa') == '1':
                        raise error.TestFail('WPA Version 1 with AES-CCM '
                                             'is not supported on Cisco')
                    cisco_types.append('aes-ccm')
                interface_conf['encryption mode'] = ('ciphers %s' %
                                                     ' '.join(cisco_types))
            elif k == 'wpa_passphrase':
                if len(v) == 64:
                    ssid_conf['wpa-psk hex'] = v
                else:
                    ssid_conf['wpa-psk ascii'] = v
            elif k in ('wpa_ptk_rekey', 'wpa_gmk_rekey'):
                # TODO(pstew): Cisco doesn't appear to be able to differentiate
                interface_conf['dot1x reauth-period'] = v
            elif k == 'wpa_strict_rekey':
                # TODO(pstew): Not implemented
                pass
            elif k == 'ieee8021x':
                if int(v):
                    raise error.TestFail('802.1x not supported on Cisco yet')
            elif k == 'ht20':
                interface_conf['channel width'] = '20'
                interface_conf['dot11 qos mode'] = 'wmm'
            elif k == 'ht40':
                interface_conf['channel width'] = '40-above'
                interface_conf['dot11 qos mode'] = 'wmm'
            elif k == 'ht40+':
                interface_conf['channel width'] = '40-above'
                interface_conf['dot11 qos mode'] = 'wmm'
            elif k == 'ht40-':
                interface_conf['channel width'] = '40-below'
                interface_conf['dot11 qos mode'] = 'wmm'
            elif k == 'shortgi':
                interface_conf['guard-interval'] = 'any'
            elif k == 'pureg':
                pass        # TODO(pstew) need Cisco support
            elif k == 'puren':
                pass        # TODO(pstew) need Cisco support
            elif k == 'protmode':
                pass        # TODO(pstew) need Cisco support
            elif k == 'ht':
                # TODO(pstew): Confirm that Cisco uses HT by default
                interface_conf['channel width'] = None
            elif k == 'htprotmode':
                pass        # TODO(pstew) need Cisco support
            elif k == 'rifs':
                pass        # TODO(pstew) need Cisco support
            elif k == '-ampdu':
                pass        # TODO(pstew) need Cisco support
            elif k == 'txpower':
                interface_conf['power local'] = cisco_power(v)
            else:
                raise error.TestFail("Unknown router config parameter %s=%s" %
                                     (k, v))

        interface_conf['ssid %s' % ssid] = ssid_conf
        self.proxy.configure({ 'interface %s' % interface: interface_conf })

        logging.info("AP configured.")

        if interface in self.ap['config']:
            self.ap['status'][interface].update(interface_conf)
        else:
            self.ap['status'][interface] = interface_conf

        self.ap['ssid'] = ssid

    def get_wifi_ip(self):
        return self.address

    def get_ssid(self):
        return self.ap['ssid']

    def cisco_power(self, value):
        if value == 'auto':
            return None
        elif value == '0':
            return '-1'
        else:
            return v

    def set_txpower(self, params):
        interface = params.get('interface', self.config.keys()[0])
        power_level = self.cisco_power(params.get('power', 'auto'))
        self.proxy.configure({ 'interface %s' % interface:
                               { 'power local': power_level } })

    def cisco_mac(self, address):
        """
        Addresses get passed in as ':' separated octets: aa:bb:cc:dd:ee:ff,
        but Cisco takes them as '.' separated words: aabb.ccdd.eeff
        """
        parts = address.split(':')
        return '.'.join(a+b for a,b in zip(parts[::2], parts[1::2]))

    def deauth(self, params):
        self.cmd('clear dot11 client %s' % self.cisco_mac(mac))

    def stop_capture(self, params):
        """
        TODO(pstew): Not yet implemented but called by default at cleanup
        """
        pass
