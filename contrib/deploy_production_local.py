#!/usr/bin/python
# Copyright (c) 2014 The Chromium OS Authors. All rights reserved.
# Use of this source code is governed by a BSD-style license that can be
# found in the LICENSE file.

"""Runs on autotest servers from a cron job to self update them.

This script is designed to run on all autotest servers to allow them to
automatically self-update based on the manifests used to create their (existing)
repos.
"""

from __future__ import print_function

import ConfigParser
import os
import subprocess
import sys
import time

import common

from autotest_lib.client.common_lib import global_config

# How long after restarting a service do we watch it to see if it's stable.
SERVICE_STABILITY_TIMER = 60


class DirtyTreeException(Exception):
    """Raised when the tree has been modified in an unexpected way."""


class UnknownCommandException(Exception):
    """Raised when we try to run a command name with no associated command."""


class UnstableServices(Exception):
    """Raised if a service appears unstable after restart."""


def verify_repo_clean():
    """This function verifies that the current repo is valid, and clean.

    @raises DirtyTreeException if the repo is not clean.
    @raises subprocess.CalledProcessError on a repo command failure.
    """
    CLEAN_STATUS_OUTPUT = 'nothing to commit (working directory clean)'

    out = subprocess.check_output(['repo', 'status'], stderr=subprocess.STDOUT)
    if out.strip() != CLEAN_STATUS_OUTPUT:
        raise DirtyTreeException(out)


def repo_versions():
    """This function collects the versions of all git repos in the general repo.

    @returns A string the describes HEAD of all git repos.
    @raises subprocess.CalledProcessError on a repo command failure.
    """
    cmd = ['repo', 'forall', '-p', '-c', 'git', 'log', '-1', '--oneline']
    return subprocess.check_output(cmd)


def repo_sync():
    """Perform a repo sync.

    @raises subprocess.CalledProcessError on a repo command failure.
    """
    subprocess.check_output(['repo', 'sync'])


def discover_update_commands():
    """Lookup the commands to run on this server.

    These commonly come from shadow_config.ini, since they vary by server type.

    @returns List of command names in string format.
    """
    try:
        return global_config.global_config.get_config_value(
                'UPDATE', 'commands', type=list)

    except (ConfigParser.NoSectionError, global_config.ConfigError):
        return []


def discover_restart_services():
    """Find the services that need restarting on the current server.

    These commonly come from shadow_config.ini, since they vary by server type.

    @returns List of service names in string format.
    """
    try:
        # From shadow_config.ini, lookup which services to restart.
        return global_config.global_config.get_config_value(
                'UPDATE', 'services', type=list)

    except (ConfigParser.NoSectionError, global_config.ConfigError):
        return []


def update_command(cmd_tag):
    """Restart a command.

    The command name is looked up in global_config.ini to find the full command
    to run, then it's executed.

    @param cmd_tag: Which command to restart.

    @raises UnknownCommandException If cmd_tag can't be looked up.
    @raises subprocess.CalledProcessError on a command failure.
    """
    # Lookup the list of commands to consider. They are intended to be
    # in global_config.ini so that they can be shared everywhere.
    cmds = dict(global_config.global_config.config.items(
        'UPDATE_COMMANDS'))

    if cmd_tag not in cmds:
        raise UnknownCommandException(cmd_tag, cmds)

    expanded_command = cmds[cmd_tag].replace('AUTOTEST_REPO',
                                              common.autotest_dir)

    print('Updating %s with: %s' % (cmd_tag, expanded_command))
    subprocess.check_call(expanded_command, shell=True)


def restart_service(service_name):
    """Restart a service.

    Restarts the standard service with "service <name> restart".

    @param service_name: The name of the service to restart.

    @raises subprocess.CalledProcessError on a command failure.
    """
    print('Restarting: %s' % service_name)
    subprocess.check_call(['sudo', 'service', service_name, 'restart'])


def service_status(service_name):
    """Return the results "status <name>" for a given service.

    This string is expected to contain the pid, and so to change is the service
    is shutdown or restarted for any reason.

    @param service_name: The name of the service to check on.
    @returns The output of the external command.
             Ex: autofs start/running, process 1931

    @raises subprocess.CalledProcessError on a command failure.
    """
    return subprocess.check_output(['sudo', 'status', service_name])


def restart_services(service_names):
    """Restart services as needed for the current server type.

    Restart the listed set of services, and watch to see if they are stable for
    at least SERVICE_STABILITY_TIMER. It restarts all services quickly,
    waits for that delay, then verifies the status of all of them.

    @param service_names: The list of service to restart and monitor.

    @raises subprocess.CalledProcessError on a command failure.
    """
    service_statuses = {}

    # Restart each, and record the status (including pid).
    for name in service_names:
        restart_service(name)
        service_statuses[name] = service_status(name)

    # Wait for a while to let the services settle.
    time.sleep(SERVICE_STABILITY_TIMER)

    # Look for any services that changed status.
    unstable_services = [n for n in service_names
                         if service_status(n) != service_statuses[n]]

    # Report any services having issues.
    if unstable_services:
        raise UnstableServices(unstable_services)


def main():
    """Main method."""
    os.chdir(common.autotest_dir)
    global_config.global_config.parse_config_file()

    try:
        print('Checking tree status:')
        verify_repo_clean()
        print('Clean.')
    except DirtyTreeException as e:
        print('Local tree is dirty, can\'t perform update safely.')
        print()
        print('repo status:')
        print(e.args[0])
        return 1

    print('Checking repository versions.')
    versions_before = repo_versions()

    print('Updating Repo.')
    repo_sync()

    print('Checking repository versions after update.')
    versions_after = repo_versions()

    if versions_before == versions_after:
        print('No change found.')
        return

    cmds = discover_update_commands()
    if cmds:
        print('Running update commands:', ', '.join(cmds))
        for cmd in cmds:
            update_command(cmd)

    services = discover_restart_services()
    if services:
        try:
            print('Restarting Services:', ', '.join(services))
            restart_services(services)
        except UnstableServices as e:
            print('The following services were not stable after the update:')
            print(e.args[0])
            return 1

    print('Current production versions:')
    print(versions_after)


if __name__ == '__main__':
    sys.exit(main())
