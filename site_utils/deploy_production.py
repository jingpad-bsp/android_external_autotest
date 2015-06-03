#!/usr/bin/python

from __future__ import print_function

import argparse
import subprocess
import sys

import common
from autotest_lib.server import frontend
from autotest_lib.site_utils.lib import infra


def discover_servers(afe, server_filter=set()):
    """Discover the in-production servers to update.

    @param afe: Server to contact with RPC requests.
    @param server_filter: A set of servers to get status for.

    @returns: A list of tuple of (server_name, server_status), the list in
              sorted by the order to be updated.
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

    # Do not update servers that need repair, and filter the server list by
    # given server_filter if needed.
    servers = [s for s in servers
               if (s['status'] != 'repair_required' and
                   (not server_filter or s['hostname'] in server_filter))]

    # Do not update devserver or crash_server (not YET supported).
    servers = [s for s in servers if 'devserver' not in s['roles'] and
               'crash_server' not in s['roles']]

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

    # Build the return list of (hostname, status)
    server_status = [(s['hostname'], s['status']) for s in servers]
    found_servers = set([s['hostname'] for s in servers])
    # Inject the servers passed in by user but not found in server database.
    for server in server_filter-found_servers:
        server_status.append((server, 'unknown'))

    return server_status


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

    print('Retrieving server status...')
    server_status = discover_servers(options.afe, set(options.servers or []))

    # Display what we plan to update.
    print('Will update (in this order):')
    for server, status in server_status:
        print('\t%-36s:\t%s' % (server, status))
    print()

    # Do the updating.
    for server, status in server_status:
        if status == 'backup':
            extra_args = ['--skip-service-status']
        else:
            extra_args = []

        cmd = ('/usr/local/autotest/site_utils/deploy_production_local.py ' +
               ' '.join(options.args + extra_args))
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
