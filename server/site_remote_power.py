# Copyright (c) 2012 The Chromium OS Authors. All rights reserved.
# Use of this source code is governed by a BSD-style license that can be
# found in the LICENSE file.

import logging, os, re, urllib

# If you create site_remote_power_config.py and remote_power_switch_machines
# there, we will use it to configure the power switch.
#
# Example configuration:
#   remote_power_switch_machines = {
#     "myserver": "rps,cyclades-acs,powerswitch1,device1,password"
#   }
try:
    from site_remote_power_config import remote_power_switch_machines
except:
    remote_power_switch_machines = {}

# If remote_power_switch_machines was not defined in site_remote_power_config,
# we look in the AFE database for a label which defines how we should behave.
#
# Here is an example label:
#   "rps,cyclades-acs,powerswitch1,device1,password"
#
# If you attach the above label to device1, then we will use the "cyclades-acs"
# powerswitch to turn the power to device1 on and off, and pass in the above
# configuration to the CycladesACSRemotePowerSwitch class.
if not remote_power_switch_machines:
    try:
        settings = 'autotest_lib.frontend.settings'
        os.environ['DJANGO_SETTINGS_MODULE'] = settings
        from autotest_lib.frontend.afe import models
        has_models = True
    except ImportError, e:
        has_models = False

# factory function for choosing which remote power class to return

def ParseConfig(config):
    type = config.split(",", 3)[1]
    cls = power_switch_types[type]
    if cls:
        return cls(config)
    else:
        raise AssertionError

def RemotePower(host):
    if remote_power_switch_machines and host in remote_power_switch_machines:
        return ParseConfig(remote_power_switch_machines[host])
    elif has_models:
        host_obj = models.Host.valid_objects.get(hostname=host)
        for label in host_obj.labels.all():
            name = label.name
            if name.startswith("rps,"):
                return ParseConfig(name)

    return None

class SentrySwitchedCDU(object):
    """
    This class implements power control for Sentry Switched CDU
    http://www.servertech.com/products/switched-pdus/

    It assumes that machine
    chromeos-rackX-hostY
    is controlled by an RPM at
    chromeos-rackX-rpm1.

    Example usage:
      switch = SentrySwitchedCDU('chromeos-rack7-host3')
      switch.set_power_off()
      switch.set_power_on()
    """


    def __init__(self, machine):
        self.machine = machine
        self.rpm_host = re.sub('host[^.]*', 'rpm1', machine, count=1)


    def set_power_on(self):
        self._set_power('on')


    def set_power_off(self):
        self._set_power('off')


    def _set_power(self, command):
        from autotest_lib.client.common_lib import pexpect
        from autotest_lib.client.common_lib import global_config
        password = global_config.global_config.get_config_value(
                'CROS', 'rpm_sentry_password', type=str)
        username = global_config.global_config.get_config_value(
                'CROS', 'rpm_sentry_username', type=str)
        rpm_host = self.rpm_host
        # In case machine comes with a full domain name, cut it off
        machine_name = self.machine.split('.', 1)[0]
        prompt = 'Switched CDU:'
        cmd = ('ssh -l %s '
               '-o StrictHostKeyChecking=no '
               '-o UserKnownHostsFile=/dev/null '
               '%s' % (username, rpm_host))
        ssh = pexpect.spawn(cmd)
        ssh.expect('Password:', timeout=30)
        ssh.sendline(password)
        ssh.expect(prompt, timeout=30)
        logging.info('Connecting to power switch (%s@%s)', username, rpm_host)
        # Command looks like: off chromeos-rack7-host3
        ssh.sendline('%s %s' %(command, machine_name))
        try:
            ssh.expect('Command successful', timeout=30)
        except pexpect.TIMEOUT:
            logging.error('Timed out while switching AC power %s for host %s',
                    command, machine_name)
            raise
        finally:
            ssh.sendline('logout')
        logging.info('Power turned %s for %s', command, machine_name)


class CycladesACSRemotePowerSwitch(object):
    """
    This class implements power control for Cyclades ACS boxes.

    The config string contains five components, separated by commas:
      1) prefix ("rps")
      2) type ("cyclades-acs")
      3) hostname of power switch box
      4) port to use on power switch box
      5) password to enter when connecting to power switch box

    Example usage:
      config = "rps,cyclades-acs,powerswitch1,device1,password"
      switch = CycladesACSRemotePowerSwitch(config)
      switch.set_power_off()
      switch.set_power_on()
    """


    def __init__(self, config):
        self.power_ip, self.power_port, self.password = config.split(",")[2:]


    def _set_power(self, state):
        from autotest_lib.client.common_lib import pexpect
        hostname = self.power_ip
        username = 'root:%s' % self.power_port
        cmd = ('ssh -l %s '
               '-o StrictHostKeyChecking=no '
               '-o UserKnownHostsFile=/dev/null '
               '%s' % (username, hostname))
        ssh = pexpect.spawn(cmd)
        ssh.expect('password:', timeout=30)
        ssh.sendline(self.password)
        ssh.expect('\n', timeout=30)
        ssh.send('\020')
        logging.info('Connecting to power switch (%s@%s)' % (username,
                                                             hostname))
        ssh.expect('Please choose an option:', timeout=30)

        if state:
           ssh.sendline('5')
           ssh.expect('Outlet turned on', timeout=30)
           logging.info('Power turned on for %s' % self.dict['power_port'])
        else:
           ssh.sendline('4')
           ssh.expect('Outlet turned off', timeout=30)
           logging.info('Power turned off for %s' % self.dict['power_port'])


    def set_power_on(self):
        self._set_power(1)


    def set_power_off(self):
        self._set_power(0)


class HTTPPowerSwitch(object):
    """
    This class implements power control via standard HTTP GET requests.

    The config string contains four components, separated by commas:
      1) prefix ("rps")
      2) type ("cyclades-acs")
      3) URL to turn power on
      4) URL to turn power off

    Example usage:
      url_prefix = "http://user:password@powerswitch1/Set.cmd?CMD=SetPower&P"
      config = "rps,http,%s1=1,%s1=0" % (url_prefix, url_prefix)
      switch = HTTPPowerSwitch(config)
      switch.set_power_off()
      switch.set_power_on()

    """


    def __init__(self, config):
        self.on_url, self.off_url = config.split(",")[2:]


    def _get_url(self, url):
        logging.info(url)
        f = urllib.urlopen(url)
        f.read()


    def set_power_on(self):
        self._get_url(self.on_url)


    def set_power_off(self):
        self._get_url(self.off_url)


power_switch_types = {
    'cyclades-acs': CycladesACSRemotePowerSwitch,
    'http': HTTPPowerSwitch
}
