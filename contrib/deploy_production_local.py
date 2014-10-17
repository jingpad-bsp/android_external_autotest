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

    print('Checking tree status:')
    out = subprocess.check_output(['repo', 'status'], stderr=subprocess.STDOUT)

    if out.strip() != CLEAN_STATUS_OUTPUT:
        print('Dirty.')
        raise DirtyTreeException(out)

    print('Clean.')


def repo_versions():
    """This function collects the versions of all git repos in the general repo.

    @returns A string the describes HEAD of all git repos.
    @raises subprocess.CalledProcessError on a repo command failure.
    """
    print('Checking repository versions.')
    cmd = ['repo', 'forall', '-p', '-c', 'git', 'log', '-1', '--oneline']
    return subprocess.check_output(cmd)


def repo_sync():
    """Perform a repo sync.

    @raises subprocess.CalledProcessError on a repo command failure.
    """
    print('Updating Repo.')
    subprocess.check_output(['repo', 'sync'], stderr=subprocess.STDOUT)


def restart_services():
    """Restart services as needed for the current server type.

    This checks the shadow_config.ini to see what should be restarted.

    @raises UnknownCommandException If shadow_config uses an unknown command.
    @raises subprocess.CalledProcessError on a command failure.
    """
    global_config.global_config.parse_config_file()

    cmd_names = ''
    service_names = ''

    try:
        # Lookup the list of commands to consider. They are intended to be
        # in global_config.ini so that they can be shared everywhere.
        cmds = dict(global_config.global_config.config.items(
            'UPDATE_COMMANDS'))

        # Lookup which commands to run. These commonly come from
        # shadow_config.ini, since they vary by server type.
        cmd_names = global_config.global_config.get_config_value(
                'UPDATE', 'commands', type=list)

    except (ConfigParser.NoSectionError, global_config.ConfigError):
        pass

    try:
        # From shadow_config.ini, lookup which services to restart.
        service_names = global_config.global_config.get_config_value(
                'UPDATE', 'services', type=list)

    except (ConfigParser.NoSectionError, global_config.ConfigError):
        pass

    if cmd_names:
        print('Running update commands....')
        for name in cmd_names:
            if name not in cmds:
                raise UnknownCommandException(name, cmds)

            expanded_command = cmds[name]
            expanded_command.replace('AUTOTEST_REPO', common.autotest_dir)

            print('Updating %s with: %s' % (name, expanded_command))
            subprocess.check_call(expanded_command, shell=True)

    if service_names:
        service_status = {}

        print('Restarting Services....')
        for name in service_names:
            print('Updating %s with: %s' % (name, expanded_command))
            subprocess.check_call(['sudo', 'service', name, 'restart'])

        def status(name):
            return subprocess.check_output(['sudo', 'status', name])

        # Record the status of each service (including pid).
        service_status = {n: status(n) for n in service_names}

        time.sleep(60)

        # Look for any services that changed status.
        unstable_services = [n for n in service_names
                             if status(n) != service_status[n]]

        # Report any services having issues.
        if unstable_names:
            raise UnstableServices(unstable_services)


def main():
    """Main method."""
    os.chdir(common.autotest_dir)

    try:
        verify_repo_clean()
    except DirtyTreeException as e:
        print('Local tree is dirty, can\'t perform update safely.')
        print()
        print('repo status:')
        print(e.args[0])
        sys.exit(1)

    versions_before = repo_versions()
    repo_sync()
    versions_after = repo_versions()

    if versions_before == versions_after:
        print('No change found.')
        return

    try:
        restart_services()
    except UnstableServices as e:
        print('The following services were not stable after the update:')
        print(e.args[0])
        sys.exit(1)

    print('Current production versions:')
    print(versions_after)


if __name__ == '__main__':
  main()
