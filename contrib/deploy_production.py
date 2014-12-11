#!/usr/bin/python

from __future__ import print_function

import argparse
import itertools
import subprocess
import sys

import common
from autotest_lib.site_utils.lib import infra


def discover_servers():
    """Discover the in-production servers to update.

    @returns A list of server host-names, in order for updates.
    """
    shards = infra.shard_servers()
    sams = infra.sam_servers()
    drones = infra.drone_servers()
    databases = infra.database_servers()
    extras = infra.extra_servers()

    # We don't manage devservers (yet).
    # devservers = infra.devserver_servers()

    # This line controls the order in which we update servers.
    return list(itertools.chain(shards, sams, drones, extras, databases))


def parse_arguments(args):
    """Parse command line arguments.

    @param args: The command line arguments to parse. (usually sys.argv[1:])

    @returns An argparse.Namespace populated with argument values.
    """
    parser = argparse.ArgumentParser(
            description='Command to update an entire autotest installation.')
    parser.add_argument('--continue', action='store_true', dest='cont',
                        help='Continue to the next server on failure.')
    parser.add_argument('--dryrun', action='store_true',
                        help='Don\'t actually run remote commands.')
    parser.add_argument('args', nargs=argparse.REMAINDER,
                        help=('deploy_production_local.py arguments'
                              ' (use -- to separate).'))

    results = parser.parse_args(args)

    # If -- was used to pass arguments to the remote processes, we don't need to
    # pass the -- along.
    if results.args and results.args[0] == '--':
        results.args.pop(0)

    return results


def main(args):
    """Main routine that drives all the real work.

    @param args: The command line arguments to parse. (usually sys.argv[1:])

    @returns The system exit code.
    """
    options = parse_arguments(args)

    print('Discover servers...')
    servers = discover_servers()
    print()

    # Display what we plan to update.
    print('Will update (in this order):')
    for server in servers:
        print('  ', server)
    print()

    # Do the updating.
    for server in servers:
        cmd = ('/usr/local/autotest/contrib/deploy_production_local.py ' +
               ' '.join(options.args))
        print('%s: %s' % (server, cmd))
        if not options.dryrun:
            try:
                out = infra.execute_command(server, cmd)
                print(out)
                print('Success')
                print()
            except subprocess.CalledProcessError as e:
                print('Error:')
                print(e.output)
                if not options.cont:
                    return 1


if __name__ == '__main__':
    sys.exit(main(sys.argv[1:]))
