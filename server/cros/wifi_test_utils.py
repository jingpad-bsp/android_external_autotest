# Copyright (c) 2013 The Chromium OS Authors. All rights reserved.
# Use of this source code is governed by a BSD-style license that can be
# found in the LICENSE file.

import datetime
import os
import re
import time

from autotest_lib.client.common_lib import error


def _get_machine_domain(hostname):
    """Parses hostname to extract machine and domain info.

    @param hostname String, machine name in wifi cell.
    @return a tuple of (string, string), domain name (if any) and machine name.

    """
    domain = ''
    machine = hostname
    if hostname.find('.') > 0:
        domain_start = hostname.find('.')
        domain = hostname[domain_start:]
        machine = hostname[0:domain_start]
    return (machine, domain)


def get_server_addr_in_lab(hostname):
    """
    If we are in the lab use the names for the server, AKA rspro, and the
    router as defined in: go/chromeos-lab-hostname-convention

    @param hostname String machine name in wifi cell
            (e.g. chromeos1-shelf1-host1.cros)
    @return String server name in cell
            (e.g. chromeos1-shelf1-host1-server.cros)

    """
    return get_router_addr_in_lab(hostname)


def get_router_addr_in_lab(hostname):
    """
    If we are in the lab use the names for the server, AKA rspro, and the
    router as defined in: go/chromeos-lab-hostname-convention

    @param hostname String machine name in wifi cell
            (e.g. chromeos1-shelf1-host1.cros)
    @return String router name in cell
            (e.g. chromeos1-shelf1-host1-router.cros)

    """
    return '%s-router%s' % _get_machine_domain(hostname)


def get_attenuator_addr_in_lab(hostname):
    """
    For wifi rate vs. range tests, look up attenuator host name.

    @param hostname String, DUT name in wifi cell.
            (e.g. chromeos3-grover-host1.cros)
    @return String, attenuator host name
            (e.g. chromeos3-grover-host1-attenuator.cros)

    """
    return '%s-attenuator%s' % _get_machine_domain(hostname)


def is_installed(host, filename):
    """
    Checks if a file exists on a remote machine.

    @param host Host object representing the remote machine.
    @param filename String path of the file to check for existence.
    @return True if filename is installed on host; False otherwise.

    """
    result = host.run('ls %s 2> /dev/null' % filename, ignore_status=True)
    m = re.search(filename, result.stdout)
    return m is not None


def get_install_path(host, filename):
    """
    Checks if a file exists on a remote machine in one of several paths.

    @param host Host object representing the remote machine.
    @param filename String name of the file to check for existence.
    @return String full path of installed file, or None if not found.

    """
    PATHS = ['/bin',
             '/sbin',
             '/system/bin',
             '/usr/bin',
             '/usr/sbin',
             '/usr/local/bin',
             '/usr/local/sbin']
    # Some hosts have poor support for which.  Sometimes none.
    result = host.run('ls {%s}/%s 2> /dev/null' % (','.join(PATHS), filename),
                      ignore_status=True)
    found_path = result.stdout.split('\n')[0].strip()
    return found_path or None


def must_be_installed(host, cmd):
    """
    Asserts that cmd is installed on a remote machine at some path and raises
    an exception if this is not the case.

    @param host Host object representing the remote machine.
    @param cmd String name of the command to check for existence.
    @return String full path of cmd on success.  Error raised on failure.

    """
    if is_installed(host, cmd):
        return cmd

    # Hunt for the equivalent file in a bunch of places.
    cmd_base = os.path.basename(cmd)
    alternate_path = get_install_path(host, cmd_base)
    if alternate_path:
        return alternate_path

    raise error.TestFail('Unable to find %s on %s' % (cmd, host.ip))


def get_interface_mac(host, ifname, command_ip):
    """Get the MAC address of a given interface on host.

    @param host host object representing remote machine.
    @param ifname string interface name.
    @param command_ip string ip command on host.
    @return string MAC address for interface on host.

    """
    result = host.run('%s link show %s' % (command_ip, ifname))
    macmatch = re.search('link/ether (\S*)', result.stdout)
    if macmatch is not None:
        return macmatch.group(1)
    return None


def sync_host_times(host_list):
    """Sync system times on test machines to our local time.

    @param host_list iterable object containing SSHHost objects.

    """
    for host in host_list:
        epoch_seconds = time.time()
        busybox_format = '%Y%m%d%H%M.%S'
        busybox_date = datetime.datetime.utcnow().strftime(busybox_format)
        host.run('date -u --set=@%s 2>/dev/null || date -u %s' % (epoch_seconds,
                                                                  busybox_date))
