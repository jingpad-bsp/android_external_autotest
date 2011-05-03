from autotest_lib.server import autotest, hosts, subcommand, test
from autotest_lib.server import utils

class iperf(test.test):
    version = 1

    def run_once(self, pair, udp, bidirectional, time, stream_list):
        print "running on %s and %s\n" % (pair[0], pair[1])

        # Designate a lable for the server side tests.
        server_label = 'net_server'

        server = hosts.create_host(pair[0])
        client = hosts.create_host(pair[1])

        # Ensure the client doesn't have the server label.
        platform_label = client.get_platform_label()
        if platform_label == server_label:
            (server, client) = (client, server)

        # Disable IPFilters if they are present.
        for m in [client, server]:
            status = m.run('iptables -L')
            if not status.exit_status:
                m.disable_ipfilters()

        # Starting a test indents the status.log entries. This test starts 2
        # additional tests causing their log entries to be indented twice. This
        # double indent confuses the parser, so reset the indent level on the
        # job, let the forked tests record their entries, then restore the
        # previous indent level.
        self.job._indenter.decrement()

        server_at = autotest.Autotest(server)
        client_at = autotest.Autotest(client)

        template = ''.join(["job.run_test('iperf', server_ip='%s', client_ip=",
                            "'%s', role='%s', udp=%s, bidirectional=%s,",
                            "test_time=%d, stream_list=%s, tag='%s')"])

        server_control_file = template % (server.ip, client.ip, 'server', udp,
                                          bidirectional, time, stream_list,
                                          'server')
        client_control_file = template % (server.ip, client.ip, 'client', udp,
                                          bidirectional, time, stream_list,
                                          'client')

        server_command = subcommand.subcommand(server_at.run,
                         [server_control_file, server.hostname],
                         subdir='../')
        client_command = subcommand.subcommand(client_at.run,
                         [client_control_file, client.hostname],
                         subdir='../')

        subcommand.parallel([server_command, client_command])

        # The parser needs a keyval file to know what host ran the test.
        utils.write_keyval('../' + server.hostname,
                           {"hostname": server.hostname})
        utils.write_keyval('../' + client.hostname,
                           {"hostname": client.hostname})

        # Restore indent level of main job.
        self.job._indenter.increment()

        for m in [client, server]:
            status = m.run('iptables -L')
            if not status.exit_status:
                m.enable_ipfilters()
