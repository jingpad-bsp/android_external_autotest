# Copyright (c) 2013 The Chromium OS Authors. All rights reserved.
# Use of this source code is governed by a BSD-style license that can be
# found in the LICENSE file.

import os
import time

from autotest_lib.client.bin import utils

class NetworkChroot(object):
    """Implements a chroot environment that runs in a separate network
    namespace from the caller.  This is useful for network tests that
    involve creating a server on the other end of a virtual ethernet
    pair.  This object is initialized with an interface name to pass
    to the chroot, as well as the IP address to assign to this
    interface, since in passing the interface into the chroot, any
    pre-configured address is removed.

    The startup of the chroot is an orchestrated process where a
    small startup script is run to perform the following tasks:
      - Write out pid file which will be a handle to the
        network namespace that that |interface| should be passed to.
      - Wait for the network namespace to be passed in, by performing
        a "sleep" and writing the pid of this process as well.  Our
        parent will kill this process to resume the startup process.
      - Manually mount /dev/pts, since the bind mount that the
        minijail0 command creates is read-only and xl2tpd is unable
        to perform operations like chown() on it which is a fatal error.
      - We can now configure the network interface with an address.
      - At this point, we can now start any user-requested server
        processes.
    """
    BIND_ROOT_DIRECTORIES = ('bin', 'dev', 'lib', 'lib32', 'lib64',
                             'proc', 'sbin', 'sys', 'usr', 'usr/local')
    ROOT_DIRECTORIES = ('etc',  'tmp', 'var', 'var/log', 'var/run')
    STARTUP = 'etc/chroot_startup.sh'
    STARTUP_DELAY_SECONDS = 5
    STARTUP_PIDFILE = 'var/run/vpn_startup.pid'
    STARTUP_SLEEPER_PIDFILE = 'var/run/vpn_sleeper.pid'

    CONFIG_FILE_TEMPLATES = {
        STARTUP:
            '#!/bin/sh\n'
            'exec > /var/log/startup.log 2>&1\n'
            'set -x\n'
            'echo $$ > /%(startup-pidfile)s\n'
            'sleep %(startup-delay-seconds)d &\n'
            'echo $! > /%(sleeper-pidfile)s &\n'
            'wait\n'
            'mount -t devpts devpts /dev/pts\n'
            'ip addr add %(local-ip-and-prefix)s dev %(local-interface-name)s\n'
            'ip link set %(local-interface-name)s up\n'
    }
    CONFIG_FILE_VALUES = {
        'sleeper-pidfile': STARTUP_SLEEPER_PIDFILE,
        'startup-delay-seconds': STARTUP_DELAY_SECONDS,
        'startup-pidfile': STARTUP_PIDFILE
    }

    def __init__(self, interface, address, prefix):
        self._interface = interface

        # Copy these values from the class-static since specific instances
        # of this class are allowed to modify their contents.
        self._root_directories = list(self.ROOT_DIRECTORIES)
        self._config_file_templates = self.CONFIG_FILE_TEMPLATES.copy()
        self._config_file_values = self.CONFIG_FILE_VALUES.copy()

        self._config_file_values.update({
            'local-interface-name': interface,
            'local-ip': address,
            'local-ip-and-prefix': '%s/%d' % (address, prefix)
        })


    def startup(self):
        """Create the chroot and start user processes."""
        self.make_chroot()
        self.write_configs()
        self.run(['/bin/bash', os.path.join('/', self.STARTUP), '&'])
        self.move_interface_to_chroot_namespace()
        self.kill_pid_file(self.STARTUP_SLEEPER_PIDFILE)


    def shutdown(self):
        """Remove the chroot filesystem in which the VPN server was running"""
        # TODO(pstew): Some processes take a while to exit, which will cause
        # the cleanup below to fail to complete successfully...
        time.sleep(5)
        utils.system_output('rm -rf --one-file-system %s' % self._temp_dir,
                            ignore_status=True)


    def add_config_templates(self, template_dict):
        """Add a filename-content dict to the set of templates for the chroot

        @param template_dict dict containing filename-content pairs for
            templates to be applied to the chroot.  The keys to this dict
            should not contain a leading '/'.

        """
        self._config_file_templates.update(template_dict)


    def add_config_values(self, value_dict):
        """Add a name-value dict to the set of values for the config template

        @param value_dict dict containing key-value pairs of values that will
            be applied to the config file templates.

        """
        self._config_file_values.update(value_dict)


    def add_root_directories(self, directories):
        """Add |directories| to the set created within the chroot.

        @param directories list/tuple containing a list of directories to
            be created in the chroot.  These elements should not contain a
            leading '/'.

        """
        self._root_directories += directories


    def add_startup_command(self, command):
        """Add a command to the script run when the chroot starts up.

        @param command string containing the command line to run.

        """
        self._config_file_templates[self.STARTUP] += '%s\n' % command


    def get_log_contents(self):
        """Return the logfiles from the chroot."""
        return utils.system_output("head -10000 %s" %
                                   os.path.join(self._temp_dir, "var/log/*"))


    def get_pid_file(self, pid_file):
        """Returns the integer contents of |pid_file| in the chroot.

        @param pid_file string containing the filename within the choot
            to read and convert to an integer.  This should not contain a
            leading '/'.

        """
        with open(os.path.join(self._temp_dir, pid_file)) as f:
            return int(f.read())


    def kill_pid_file(self, pid_file):
        """Kills the process belonging to |pid_file| in the chroot.

        @param pid_file string filename within th chroot to gain the process ID
            which this method will kill.

        """
        utils.system('kill %d' % self.get_pid_file(pid_file),
                     ignore_status=True)


    def make_chroot(self):
        """Make a chroot filesystem."""
        self._temp_dir = utils.system_output('mktemp -d /tmp/chroot.XXXXXXXXX')
        for rootdir in self._root_directories:
            os.mkdir(os.path.join(self._temp_dir, rootdir))

        self._jail_args = []
        for rootdir in self.BIND_ROOT_DIRECTORIES:
            src_path = os.path.join('/', rootdir)
            dst_path = os.path.join(self._temp_dir, rootdir)
            if not os.path.exists(src_path):
                continue
            elif os.path.islink(src_path):
                link_path = os.readlink(src_path)
                os.symlink(link_path, dst_path)
            else:
                os.mkdir(dst_path)
                self._jail_args += [ '-b', '%s,%s' % (src_path, src_path) ]


    def move_interface_to_chroot_namespace(self):
        """Move network interface to the network namespace of the server."""
        utils.system('ip link set %s netns %d' %
                     (self._interface, self.get_pid_file(self.STARTUP_PIDFILE)))


    def run(self, args):
        """Run a command in a chroot, within a separate network namespace.

        @param args list containing the command line arguments to run.

        """
        utils.system('minijail0 -e -C %s %s' %
                     (self._temp_dir, ' '.join(self._jail_args + args)))


    def write_configs(self):
        """Write out config files"""
        for config_file, template in self._config_file_templates.iteritems():
            with open(os.path.join(self._temp_dir, config_file), 'w') as f:
                f.write(template % self._config_file_values)
