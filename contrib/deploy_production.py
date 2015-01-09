#!/usr/bin/python

from __future__ import print_function

import argparse
import subprocess
import sys

import common
from autotest_lib.server import frontend
from autotest_lib.site_utils.lib import infra


def discover_servers(afe):
    """Discover the in-production servers to update.

    @param afe: Server to contact with RPC requests.

    @returns A list of server host-names, in order for updates.
    """
    # Example server details....
    # {
    #     'hostname': 'server1',
    #     'status': 'backup',
    #     'roles': ['drone', 'scheduler'],
    #     'attributes': {'max_processes': 300}
    # }
    rpc = frontend.AFE(server=afe)
    servers = rpc.run('get_servers')

    # Do not update servers that need repair.
    servers = [s for s in servers if s['status'] != 'repair_required']

    # Do not update devservers (not YET supported).
    servers = [s for s in servers if 'devserver' not in s['roles']]

    def update_order(s):
        """Sort order for updating servers (lower first).

        @param s: Server details for a single server.
        """
        if 'database' in s['roles']:
            return 0
        if 'scheduler' in s['roles']:
            return 1
        return 2

    # Order in which servers are updated.
    servers.sort(key=update_order)

    return [s['hostname'] for s in servers]


def parse_arguments(args):
    """Parse command line arguments.

    @param args: The command line arguments to parse. (usually sys.argv[1:])

    @returns An argparse.Namespace populated with argument values.
    """
    parser = argparse.ArgumentParser(
            formatter_class=argparse.RawDescriptionHelpFormatter,
            description='Command to update an entire autotest installation.',
            epilog=('Update all servers:\n'
                    '  deploy_production.py\n'
                    '\n'
                    'Update one server:\n'
                    '  deploy_production.py <server>\n'
                    '\n'
                    'Send arguments to remote deploy_production_local.py:\n'
                    '  deploy_production.py -- --dryrun\n'
                    '\n'
                    'See what arguments would be run on specified servers:\n'
                    '  deploy_production.py --dryrun <server_a> <server_b> --'
                    ' --skip-update\n'))

    parser.add_argument('--continue', action='store_true', dest='cont',
            help='Continue to the next server on failure.')
    parser.add_argument('--afe', default='cautotest',
            help='What is the main server for this installation? (cautotest).')
    parser.add_argument('--dryrun', action='store_true',
            help='Don\'t actually run remote commands.')
    parser.add_argument('args', nargs=argparse.REMAINDER,
            help=('<server>, <server> ... -- <remote_arg>, <remote_arg> ...'))

    results = parser.parse_args(args)

    # We take the args list and further split it down. Everything before --
    # is a server name, and everything after it is an argument to pass along
    # to deploy_production_local.py.
    #
    # This:
    #   server_a, server_b -- --dryrun --skip-report
    #
    # Becomes:
    #   args.servers['server_a', 'server_b']
    #   args.args['--dryrun', '--skip-report']
    try:
        local_args_index = results.args.index('--') + 1
    except ValueError:
        # If -- isn't present, they are all servers.
        results.servers = results.args
        results.args = []
    else:
        # Split arguments.
        results.servers = results.args[:local_args_index-1]
        results.args = results.args[local_args_index:]

    return results


def main(args):
    """Main routine that drives all the real work.

    @param args: The command line arguments to parse. (usually sys.argv[1:])

    @returns The system exit code.
    """
    options = parse_arguments(args)

    if not options.servers:
        print('Discover servers...')
        options.servers = discover_servers(options.afe)
        print()

    # Display what we plan to update.
    print('Will update (in this order):')
    for server in options.servers:
        print('  ', server)
    print()

    # Do the updating.
    for server in options.servers:
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
