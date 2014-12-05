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
import argparse
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


def update_command(cmd_tag, dryrun=False):
    """Restart a command.

    The command name is looked up in global_config.ini to find the full command
    to run, then it's executed.

    @param cmd_tag: Which command to restart.
    @param dryrun: If true print the command that would have been run.

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

    if dryrun:
        print('Would have updated %s via "%s"' % (cmd_tag, expanded_command))
    else:
        print('Updating %s with: %s' % (cmd_tag, expanded_command))
        subprocess.check_call(expanded_command, shell=True)


def restart_service(service_name, dryrun=False):
    """Restart a service.

    Restarts the standard service with "service <name> restart".

    @param service_name: The name of the service to restart.
    @param dryrun: Don't really run anything, just print out the command.

    @raises subprocess.CalledProcessError on a command failure.
    """
    cmd = ['sudo', 'service', service_name, 'restart']
    if dryrun:
        print('Would have restarted %s via "%s"' %
              (service_name, ' '.join(cmd)))
    else:
        print('Restarting: %s' % service_name)
        subprocess.check_call(cmd)


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


def restart_services(service_names, dryrun=False):
    """Restart services as needed for the current server type.

    Restart the listed set of services, and watch to see if they are stable for
    at least SERVICE_STABILITY_TIMER. It restarts all services quickly,
    waits for that delay, then verifies the status of all of them.

    @param service_names: The list of service to restart and monitor.
    @param dryrun: Don't really restart the service, just print out the command.

    @raises subprocess.CalledProcessError on a command failure.
    @raises UnstableServices if any services are unstable after restart.
    """
    service_statuses = {}

    if dryrun:
        for name in service_names:
            restart_service(name, dryrun=True)
        return

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


def run_deploy_actions(dryrun=False):
    """

    @param dryrun: Don't really restart the service, just print out the command.

    @raises subprocess.CalledProcessError on a command failure.
    @raises UnstableServices if any services are unstable after restart.
    """
    cmds = discover_update_commands()
    if cmds:
        print('Running update commands:', ', '.join(cmds))
        for cmd in cmds:
            update_command(cmd, dryrun=dryrun)

    services = discover_restart_services()
    if services:
        print('Restarting Services:', ', '.join(services))
        restart_services(services, dryrun=dryrun)


def parse_arguments(args):
    """Parse command line arguments.

    @param args: The command line arguments to parse. (ususally sys.argsv[1:])

    @returns A Behaviors named tuple that defines what actions we should run.
    """
    parser = argparse.ArgumentParser(
            description='Command to update an autotest server.')
    parser.add_argument('--skip-verify', action='store_false',
                        dest='verify', default=True,
                        help='Disable verification of a clean repository.')
    parser.add_argument('--skip-update', action='store_false',
                        dest='update', default=True,
                        help='Skip the repository source code update.')
    parser.add_argument('--skip-actions', action='store_false',
                        dest='actions', default=True,
                        help='Skip the post update actions.')
    parser.add_argument('--skip-report', action='store_false',
                        dest='report', default=True,
                        help='Skip the git version report.')
    parser.add_argument('--actions-only', action='store_true',
                        help='Run the post update actions (restart services).')
    parser.add_argument('--dryrun', action='store_true',
                        help='Don\'t actually run any commands, just log.')

    results = parser.parse_args(args)

    if results.actions_only:
        results.verify = False
        results.update = False
        results.report = False

    # TODO(dgarrett): Make these behaviors support dryrun.
    if results.dryrun:
        results.verify = False
        results.update = False

    return results


def main(args):
    """Main method."""
    os.chdir(common.autotest_dir)
    global_config.global_config.parse_config_file()

    behaviors = parse_arguments(args)

    if behaviors.verify:
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

    if behaviors.update:
        print('Checking repository versions.')
        versions_before = repo_versions()

        print('Updating Repo.')
        repo_sync()

        print('Checking repository versions after update.')
        if versions_before == repo_versions():
            print('No change found.')
            return

    if behaviors.actions:
        try:
            run_deploy_actions(dryrun=behaviors.dryrun)
        except UnstableServices as e:
            print('The following services were not stable after '
                  'the update:')
            print(e.args[0])
            return 1

    if behaviors.report:
        print('Current production versions:')
        print(repo_versions())


if __name__ == '__main__':
    sys.exit(main(sys.argv[1:]))
