# Copyright (c) 2013 The Chromium OS Authors. All rights reserved.
# Use of this source code is governed by a BSD-style license that can be
# found in the LICENSE file.

import dbus
import logging
import os
import tempfile
import time
import ConfigParser

from autotest_lib.client.bin import utils
from autotest_lib.client.common_lib import error


def avahi_config(options, src_file='/etc/avahi/avahi-daemon.conf'):
    """Creates a temporary avahi-daemon.conf file with the specified changes.

    Avahi daemon uses a text configuration file with sections and values
    assigned to options on that section. This function creates a new config
    file based on the one provided and a set of changes. The changes are
    specified as triples of section, option and value that override the existing
    options on the config file. If a value of None is specified for any triplet,
    the corresponding option will be removed from the file.

    @param options: A list of triplets of the form (section, option, value).
    @param src_file: The default config file to use as a base for the changes.
    @return: The filename of a temporary file with the new configuration file.
    """

    conf = ConfigParser.SafeConfigParser()
    conf.read(src_file)

    for section, option, value in options:
        if value is None:
            conf.remove_option(section, option)
        else:
            conf.set(section, option, value)

    fd, tempfn = tempfile.mkstemp(prefix='avahi-conf')
    os.close(fd)
    conf.write(open(tempfn, 'w'))
    return tempfn


def avahi_ping():
    """Returns True when the avahi-deamon's DBus interface is ready.

    After your launch avahi-daemon, there is a short period of time where the
    daemon is running but the DBus interface isn't ready yet. This functions
    blocks for a few seconds waiting for a ping response from the DBus API
    and returns wether it got a response.
    """
    bus = dbus.SystemBus()
    try:
        ret = bus.call_blocking(
                bus_name='org.freedesktop.Avahi', object_path='/',
                dbus_interface='org.freedesktop.Avahi.Server',
                method='GetState',
                signature='', args=[], timeout=2.0)
    except dbus.exceptions.DBusException:
        return False
    logging.debug('org.freedesktop.Avahi.GetState() = %r', ret)
    return ret == 2 # AVAHI_ENTRY_GROUP_ESTABLISHED


def avahi_start(config_file=None):
    """Start avahi-daemon with the provided config file.

    This function waits until the avahi-daemon is ready listening on the DBus
    interface. If avahi fails to be ready after 10 seconds, an error is raised.

    @param config_file: The filename of the avahi-daemon config file or None to
    use the default.
    """
    env = ''
    if not config_file is None:
        env = 'AVAHI_DAEMON_CONF="%s" ' % config_file
    utils.system(env + 'start avahi', ignore_status=False)
    # Wait until avahi is ready.
    deadline = time.time() + 10.
    while time.time() < deadline:
        if avahi_ping():
            return
        time.sleep(0.1)
    raise error.TestError("avahi-daemon isn't ready after 10s running.")


def avahi_stop():
    """Stop the avahi daemon."""
    utils.system('stop avahi')
