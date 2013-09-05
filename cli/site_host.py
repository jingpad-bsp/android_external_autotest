# Copyright (c) 2011 The Chromium OS Authors. All rights reserved.
# Use of this source code is governed by a BSD-style license that can be
# found in the LICENSE file.

import common
import inspect, new, socket, sys

from autotest_lib.client.bin import utils
from autotest_lib.cli import topic_common, host
from autotest_lib.server import hosts
from autotest_lib.client.common_lib import error


# In order for hosts to work correctly, some of its variables must be setup.
hosts.factory.ssh_user = 'root'
hosts.factory.ssh_pass = ''
hosts.factory.ssh_port = 22
hosts.factory.ssh_verbosity_flag = ''
hosts.factory.ssh_options = ''


class site_host(host.host):
    pass


class site_host_create(site_host, host.host_create):
    """
    site_host_create subclasses host_create in host.py.
    """


    def _execute_add_one_host(self, host):
        # Always add the hosts as locked to avoid the host
        # being picked up by the scheduler before it's ACL'ed
        self.data['locked'] = True
        self.execute_rpc('add_host', hostname=host,
                         status="Ready", **self.data)
        # If there are labels avaliable for host, use them.
        host_info = self.host_info_map[host]
        if host_info.labels:
            labels = list(set(self.labels[:] + host_info.labels))
        else:
            labels = self.labels[:]
        # Now add the platform label
        if self.platform:
            labels.append(self.platform)
        elif host_info.platform:
            # If a platform was not provided and we were able to retrieve it
            # from the host, use the retrieved platform.
            labels.append(host_info.platform)
        if len(labels):
            self.execute_rpc('host_add_labels', id=host, labels=labels)


    def execute(self):
        # Check to see if the platform or any other labels can be grabbed from
        # the hosts.
        self.host_info_map = {}
        for host in self.hosts:
            try:
                if utils.ping(host, tries=1, deadline=1) == 0:
                    ssh_host = hosts.create_host(host)
                    host_info = host_information(host,
                                                 ssh_host.get_platform(),
                                                 ssh_host.get_labels())
                else:
                    # Can't ping the host, use default information.
                    host_info = host_information(host, None, [])
            except (socket.gaierror, error.AutoservRunError,
                    error.AutoservSSHTimeout):
                # We may be adding a host that does not exist yet or we can't
                # reach due to hostname/address issues or if the host is down.
                host_info = host_information(host, None, [])
            self.host_info_map[host] = host_info
        # We need to check if these labels & ACLs exist,
        # and create them if not.
        if self.platform:
            self.check_and_create_items('get_labels', 'add_label',
                                        [self.platform],
                                        platform=True)
        else:
            # No platform was provided so check and create the platform label
            # for each host.
            platforms = []
            for host_info in self.host_info_map.values():
                if host_info.platform and host_info.platform not in platforms:
                    platforms.append(host_info.platform)
            if len(platforms):
                self.check_and_create_items('get_labels', 'add_label',
                                            platforms,
                                            platform=True)
        labels_to_check_and_create = self.labels[:]
        for host_info in self.host_info_map.values():
            labels_to_check_and_create = (host_info.labels +
                                          labels_to_check_and_create)
        if labels_to_check_and_create:
            self.check_and_create_items('get_labels', 'add_label',
                                        labels_to_check_and_create,
                                        platform=False)

        if self.acls:
            self.check_and_create_items('get_acl_groups',
                                        'add_acl_group',
                                        self.acls)

        success = self.site_create_hosts_hook()

        if len(success):
            for acl in self.acls:
                self.execute_rpc('acl_group_add_hosts', id=acl, hosts=success)

            if not self.locked:
                for host in success:
                    self.execute_rpc('modify_host', id=host, locked=False)
        return success


class host_information(object):
    """Store host information so we don't have to keep looking it up."""


    def __init__(self, hostname, platform, labels):
        self.hostname = hostname
        self.platform = platform
        self.labels = labels


# Any classes we don't override in host should be copied automatically
for cls in [getattr(host, n) for n in dir(host) if not n.startswith("_")]:
    if not inspect.isclass(cls):
        continue
    cls_name = cls.__name__
    site_cls_name = 'site_' + cls_name
    if hasattr(sys.modules[__name__], site_cls_name):
        continue
    bases = (site_host, cls)
    members = {'__doc__': cls.__doc__}
    site_cls = new.classobj(site_cls_name, bases, members)
    setattr(sys.modules[__name__], site_cls_name, site_cls)
